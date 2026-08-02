/**
 * MAP Backend Server
 *
 * Purpose: Orchestrate agents via REST API
 * - Coordinates 19 agents: 5 PM agents (gimena, gabi, gabriela, santi, daniel)
 *   + 14 spec-kit agents (architect, fullstack-developer, ..., loaded from
 *   ia-hybrid-teams/agents/*.md)
 * - Manages projects and their lifecycle
 * - Validates phase/step combinations against ia-hybrid-teams/spec-kit/PHASE_CONTRACTS.md
 * - Integrates with AgentEvaluator for real quality scoring
 * - Real API-key authentication (see middleware/auth.js)
 * - Storage via src/store.js: plain files locally, Vercel KV in serverless
 *
 * Usage (local):
 * npm install
 * node src/server.js
 *
 * Usage (Vercel): deployed via api/map.js, mounted under the /map prefix —
 * see the prefix-stripping middleware below.
 *
 * Endpoints:
 * GET    /health
 * GET    /agents                  - List all invokable agents
 * GET    /phases                  - List phase contracts
 * GET    /phases/:idOrKey         - Get one phase contract
 * POST   /projects                - Create project
 * GET    /projects                - List projects
 * GET    /projects/:id            - Get project state
 * POST   /orchestrate             - Run next agent for a project's phase/step
 * POST   /agents/:name/invoke     - Invoke specific agent
 * POST   /evaluate                - Evaluate agent output (real rubric via AgentEvaluator)
 * POST   /brain/ingest-acta       - Feed a meeting acta to Gabriela; she extracts
 *                                    decisions/alerts into the project's Brain
 */

const express = require("express");
const cors = require("cors");
require("dotenv").config();
const Anthropic = require("@anthropic-ai/sdk");

const { authenticateToken } = require("./middleware/auth");
const agentRegistry = require("./agents/registry");
const phaseContracts = require("./phases/phaseContracts");
const AgentEvaluator = require("./agent-evaluator");
const store = require("./store");

const app = express();
const PORT = process.env.PORT || 3001;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;

// On Vercel this app is reached via a rewrite from /map/(.*) to /api/map, but
// the request URL the function sees is still the original /map/... path —
// strip the prefix so routes below can stay mounted at root either way.
app.use((req, res, next) => {
  if (req.url === "/map" || req.url.startsWith("/map/")) {
    req.url = req.url.slice(4) || "/";
  }
  next();
});

app.use(cors());
app.use(express.json());

const client = new Anthropic({ apiKey: ANTHROPIC_API_KEY });
const evaluator = new AgentEvaluator(ANTHROPIC_API_KEY);

// Health check stays unauthenticated on purpose: deploy platforms (Railway,
// Render, Vercel, etc.) probe this over plain HTTP with no API key to decide
// whether to route traffic to the instance.
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || "development",
    storage: store.usingKV ? "vercel-kv" : "filesystem"
  });
});

app.use(authenticateToken);

// ============================================================================
// AGENTS
// ============================================================================

app.get("/agents", (req, res) => {
  res.json(agentRegistry.listAgents());
});

// ============================================================================
// PHASES
// ============================================================================

app.get("/phases", (req, res) => {
  res.json(phaseContracts.listPhases());
});

app.get("/phases/:idOrKey", (req, res) => {
  const phase = phaseContracts.getPhase(req.params.idOrKey);
  if (!phase) return res.status(404).json({ error: "Phase not found" });
  res.json(phase);
});

// ============================================================================
// PROJECT MANAGEMENT
// ============================================================================

function defaultProjectBrain() {
  return { status: "pending", decisionLog: [], alerts: [], meetingLog: [] };
}

function newProjectRecord({ id, name, owner, description, phase }) {
  return {
    id,
    name,
    owner,
    description,
    currentPhase: phase || 1,
    currentStep: "iniciando",
    status: "active",
    progress: 0,
    createdAt: new Date().toISOString(),
    memory: {
      projectBrain: defaultProjectBrain(),
      backlogs: {
        hu: { status: "pending", ids: [] },
        plans: { status: "pending", plans: [] },
        actas: { status: "pending", actas: [] }
      },
      sprints: { current: 1, status: "pending" },
      timeline: { createdAt: new Date().toISOString(), activities: [] }
    }
  };
}

// Projects created before decisionLog/alerts/meetingLog existed won't have
// them — backfill defensively rather than crashing on .push().
function ensureBrainShape(project) {
  project.memory.projectBrain = project.memory.projectBrain || {};
  project.memory.projectBrain.decisionLog = project.memory.projectBrain.decisionLog || [];
  project.memory.projectBrain.alerts = project.memory.projectBrain.alerts || [];
  project.memory.projectBrain.meetingLog = project.memory.projectBrain.meetingLog || [];
  return project;
}

app.get("/projects", async (req, res) => {
  try {
    res.json(await store.readProjects());
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get("/projects/:id", async (req, res) => {
  try {
    const projects = await store.readProjects();
    const project = projects.find((p) => p.id === req.params.id);
    if (!project) return res.status(404).json({ error: "Project not found" });
    res.json(project);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/projects", async (req, res) => {
  try {
    const { name, owner, description, phase } = req.body;
    const newProject = newProjectRecord({
      id: `Proyecto_${Date.now()}`,
      name,
      owner,
      description,
      phase
    });

    const projects = await store.readProjects();
    projects.push(newProject);
    await store.writeProjects(projects);

    res.status(201).json(newProject);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// AGENT INVOCATION
// ============================================================================

// Shared by the /agents/:name/invoke route AND /orchestrate — no internal
// HTTP call to itself. That pattern relied on `localhost` being reachable,
// which isn't true across serverless invocations (and was wasteful even
// locally: same process, two network round-trips for one Claude call).
async function invokeAgentCore(name, projectId, input, context) {
  if (!agentRegistry.isKnownAgent(name)) {
    const err = new Error(`Unknown agent: ${name}`);
    err.status = 400;
    throw err;
  }

  const prompt = agentRegistry.buildPrompt(name, input, context);
  const { model, maxTokens } = agentRegistry.getModelConfig(name);
  const requestPayload = {
    model,
    max_tokens: maxTokens,
    messages: [{ role: "user", content: prompt.user }]
  };
  if (prompt.system) {
    requestPayload.system = prompt.system;
  }

  const response = await client.messages.create(requestPayload);

  const result = {
    agent: name,
    projectId,
    timestamp: new Date().toISOString(),
    output: response.content[0].text,
    usage: response.usage,
    model
  };

  await store.logActivity({
    timestamp: result.timestamp,
    projectId,
    agent: name,
    action: "invoked",
    status: "completed"
  });

  return result;
}

app.post("/agents/:name/invoke", async (req, res) => {
  try {
    const { name } = req.params;
    const { projectId, input, context } = req.body;
    const result = await invokeAgentCore(name, projectId, input, context);
    res.json(result);
  } catch (error) {
    res.status(error.status || 500).json({ error: error.message });
  }
});

// ============================================================================
// ORCHESTRATION
// ============================================================================

// Which agent handles a given (phase, step) — validated against phaseContracts
// so we never invoke an agent that isn't actually assigned to that phase.
//
// Phase 1 steps follow esquema-planeacion.md's 7 sub-phases (0-6) in order —
// see phaseContracts.js's PLANNING_SUB_PHASES for objective/output/gate per step.
//
// santi/daniel (actas, release notes) are intentionally NOT here: they aren't
// tied to a single phase step, they run continuously across the whole
// lifecycle. Invoke them directly via /agents/:name/invoke instead of through
// /orchestrate. (They used to be mapped to "3:meeting_minutes"/"3:release_notes"
// here, but neither is in Phase 3's agent list in phaseContracts.js, so those
// calls always 400'd — removed rather than fixed, since forcing them into one
// phase was the wrong model to begin with.)
const STEP_TO_AGENT = {
  "1:lock_scope": "gimena",
  "1:milestones": "milestone-writer",
  "1:dod": "dod-definer",
  "1:estimation": "gabi",
  "1:reconciliation": "capacity-reconciler",
  "1:timeline": "gina-scheduler",
  "1:transversales": "auditor",
  "2:data_model": "data-engineer",
  "2:work_plan": "gabi",
  "2:review": "auditor",
  "3:frontend_web": "fullstack-developer",
  "3:frontend_app": "flutter-developer",
  "3:integration": "integration",
  "4:sonar_gate": "sonar-quality-gate",
  "4:unit_test_review": "unit-test-standards-reviewer",
  "4:quality_report": "quality-report-generator"
};

app.post("/orchestrate", async (req, res) => {
  try {
    const { projectId, phase, step } = req.body;

    const phaseContract = phaseContracts.getPhase(phase);
    if (!phaseContract) {
      return res.status(400).json({ error: `Unknown phase: ${phase}` });
    }

    const agentToInvoke = STEP_TO_AGENT[`${phaseContract.id}:${step}`];
    if (!agentToInvoke) {
      return res.status(400).json({
        error: `No agent mapped for phase "${phaseContract.key}" step "${step}"`,
        availableSteps: Object.keys(STEP_TO_AGENT)
          .filter((k) => k.startsWith(`${phaseContract.id}:`))
          .map((k) => k.split(":")[1])
      });
    }

    if (!phaseContract.agents.includes(agentToInvoke)) {
      return res.status(400).json({
        error: `Agent "${agentToInvoke}" is not assigned to phase "${phaseContract.key}" per PHASE_CONTRACTS.md`,
        phaseAgents: phaseContract.agents
      });
    }

    const projects = await store.readProjects();
    const project = projects.find((p) => p.id === projectId);
    if (!project) {
      return res.status(404).json({ error: "Project not found" });
    }

    const agentResult = await invokeAgentCore(agentToInvoke, projectId, step, {
      phase: phaseContract.key,
      step
    });

    project.currentPhase = phaseContract.id;
    project.currentStep = step;
    project.progress = Math.min(project.progress + 15, 95);
    project.memory.timeline.activities.push({
      timestamp: new Date().toISOString(),
      agent: agentToInvoke,
      action: `${step} completed`,
      status: "completed"
    });

    await store.writeProjects(projects);

    res.json({
      projectId,
      phase: phaseContract.key,
      step,
      agentInvoked: agentToInvoke,
      agentResult: agentResult.output,
      projectUpdated: project
    });
  } catch (error) {
    res.status(error.status || 500).json({ error: error.message });
  }
});

// ============================================================================
// EVALUATION (real rubric via AgentEvaluator, not an inline duplicate)
// ============================================================================

app.post("/evaluate", async (req, res) => {
  try {
    const { agentName, output, context } = req.body;

    if (!agentRegistry.isKnownAgent(agentName)) {
      return res.status(400).json({ error: `Unknown agent: ${agentName}` });
    }

    const result = await evaluator.evaluate(agentName, output, context);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// PROJECT BRAIN — acta ingestion
// ============================================================================

// 1. An acta gets created (Santi on-demand, or the Proyecto Actas Apps Script
//    automatically) → 2. its content + metadata is POSTed here → 3. Gabriela
//    reads it and extracts decisions (Decision Log) and risks (Alerts) →
//    4. the project's Brain is updated. If no project matches `projectName`
//    yet, one is created so the Brain still gets the entry.
app.post("/brain/ingest-acta", async (req, res) => {
  try {
    const { projectName, actaContent, metadata } = req.body;

    if (!projectName || !actaContent) {
      return res.status(400).json({ error: "projectName and actaContent are required" });
    }

    const projects = await store.readProjects();
    let project = projects.find((p) => p.name === projectName);

    if (!project) {
      project = newProjectRecord({
        id: `Proyecto_${Date.now()}`,
        name: projectName,
        owner: (metadata && metadata.attendees) || "unknown",
        description: `Auto-creado desde acta de reunión: ${(metadata && metadata.meetingTitle) || projectName}`
      });
      projects.push(project);
    }

    ensureBrainShape(project);

    const prompt = agentRegistry.buildActaIngestPrompt(actaContent, metadata);
    const { model, maxTokens } = agentRegistry.getModelConfig("gabriela");
    const response = await client.messages.create({
      model,
      max_tokens: maxTokens,
      messages: [{ role: "user", content: prompt }]
    });

    const text = response.content[0].text;
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    const parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : { decisions: [], alerts: [] };

    const timestamp = new Date().toISOString();
    const source = (metadata && metadata.docLink) || null;

    (parsed.decisions || []).forEach((d) => {
      project.memory.projectBrain.decisionLog.push({ ...d, timestamp, source });
    });
    (parsed.alerts || []).forEach((a) => {
      project.memory.projectBrain.alerts.push({ ...a, timestamp, status: "open", source });
    });
    project.memory.projectBrain.meetingLog.push({
      timestamp,
      meetingTitle: (metadata && metadata.meetingTitle) || null,
      docLink: source,
      date: (metadata && metadata.date) || null
    });
    project.memory.projectBrain.status = "active";

    project.memory.timeline.activities.push({
      timestamp,
      agent: "gabriela",
      action: "acta ingerida al Project Brain",
      status: "completed"
    });

    await store.writeProjects(projects);

    res.json({
      projectId: project.id,
      projectName: project.name,
      decisionsAdded: (parsed.decisions || []).length,
      alertsAdded: (parsed.alerts || []).length,
      brain: project.memory.projectBrain
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// START SERVER (local/self-hosted only — Vercel requires the app, not a listener)
// ============================================================================

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`MAP Backend Server running on port ${PORT}`);
    console.log(`Anthropic API key: ${ANTHROPIC_API_KEY ? "configured" : "MISSING"}`);
    console.log(`Storage: ${store.usingKV ? "Vercel KV" : "filesystem"}`);
    console.log(`Spec-kit agents dir: ${agentRegistry.SPEC_KIT_AGENTS_DIR}`);
  });
}

module.exports = app;
