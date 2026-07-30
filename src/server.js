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
 *
 * Usage:
 * npm install
 * node src/server.js
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
const fs = require("fs");
const path = require("path");

const { authenticateToken } = require("./middleware/auth");
const agentRegistry = require("./agents/registry");
const phaseContracts = require("./phases/phaseContracts");
const AgentEvaluator = require("./agent-evaluator");

const app = express();
const PORT = process.env.PORT || 3001;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const STORAGE_DIR = process.env.STORAGE_DIR || path.join(__dirname, "..", "storage");

app.use(cors());
app.use(express.json());

const client = new Anthropic({ apiKey: ANTHROPIC_API_KEY });
const evaluator = new AgentEvaluator(ANTHROPIC_API_KEY);

if (!fs.existsSync(STORAGE_DIR)) {
  fs.mkdirSync(STORAGE_DIR, { recursive: true });
}

// Health check stays unauthenticated on purpose: deploy platforms (Railway,
// Render, etc.) probe this over plain HTTP with no API key to decide whether
// to route traffic to the instance.
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || "development"
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

function projectsFilePath() {
  return path.join(STORAGE_DIR, "projects.json");
}

function readProjects() {
  const file = projectsFilePath();
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeProjects(projects) {
  fs.writeFileSync(projectsFilePath(), JSON.stringify(projects, null, 2));
}

function defaultProjectBrain() {
  return { status: "pending", decisionLog: [], alerts: [], meetingLog: [] };
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

app.get("/projects", (req, res) => {
  try {
    res.json(readProjects());
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get("/projects/:id", (req, res) => {
  try {
    const project = readProjects().find((p) => p.id === req.params.id);
    if (!project) return res.status(404).json({ error: "Project not found" });
    res.json(project);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/projects", (req, res) => {
  try {
    const { name, owner, description, phase } = req.body;

    const newProject = {
      id: `Proyecto_${Date.now()}`,
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
        timeline: {
          createdAt: new Date().toISOString(),
          activities: []
        }
      }
    };

    const projects = readProjects();
    projects.push(newProject);
    writeProjects(projects);

    res.status(201).json(newProject);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// AGENT INVOCATION
// ============================================================================

app.post("/agents/:name/invoke", async (req, res) => {
  try {
    const { name } = req.params;
    const { projectId, input, context } = req.body;

    if (!agentRegistry.isKnownAgent(name)) {
      return res.status(400).json({ error: `Unknown agent: ${name}` });
    }

    const prompt = agentRegistry.buildPrompt(name, input, context);
    const messages = [{ role: "user", content: prompt.user }];

    const requestPayload = {
      model: "claude-3-5-haiku-20241022",
      max_tokens: 2000,
      messages
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
      usage: response.usage
    };

    logActivity(projectId, name, "invoked", "completed");

    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// ORCHESTRATION
// ============================================================================

// Which agent handles a given (phase, step) — validated against phaseContracts
// so we never invoke an agent that isn't actually assigned to that phase.
const STEP_TO_AGENT = {
  "1:project_brain": "gabriela",
  "1:user_stories": "gimena",
  "1:scheduling": "gina-scheduler",
  "2:data_model": "data-engineer",
  "2:work_plan": "gabi",
  "2:review": "auditor",
  "3:frontend_web": "fullstack-developer",
  "3:frontend_app": "flutter-developer",
  "3:integration": "integration",
  "4:sonar_gate": "sonar-quality-gate",
  "4:unit_test_review": "unit-test-standards-reviewer",
  "4:quality_report": "quality-report-generator",
  "3:meeting_minutes": "santi",
  "3:release_notes": "daniel"
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

    const projects = readProjects();
    const project = projects.find((p) => p.id === projectId);
    if (!project) {
      return res.status(404).json({ error: "Project not found" });
    }

    const agentResponse = await fetch(`http://localhost:${PORT}/agents/${agentToInvoke}/invoke`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${req.token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        projectId,
        input: step,
        context: { phase: phaseContract.key, step }
      })
    });

    if (!agentResponse.ok) {
      throw new Error("Agent invocation failed");
    }

    const agentResult = await agentResponse.json();

    project.currentPhase = phaseContract.id;
    project.currentStep = step;
    project.progress = Math.min(project.progress + 15, 95);
    project.memory.timeline.activities.push({
      timestamp: new Date().toISOString(),
      agent: agentToInvoke,
      action: `${step} completed`,
      status: "completed"
    });

    writeProjects(projects);

    res.json({
      projectId,
      phase: phaseContract.key,
      step,
      agentInvoked: agentToInvoke,
      agentResult: agentResult.output,
      projectUpdated: project
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
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

    const projects = readProjects();
    let project = projects.find((p) => p.name === projectName);

    if (!project) {
      project = {
        id: `Proyecto_${Date.now()}`,
        name: projectName,
        owner: (metadata && metadata.attendees) || "unknown",
        description: `Auto-creado desde acta de reunión: ${(metadata && metadata.meetingTitle) || projectName}`,
        currentPhase: 1,
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
      projects.push(project);
    }

    ensureBrainShape(project);

    const prompt = agentRegistry.buildActaIngestPrompt(actaContent, metadata);
    const response = await client.messages.create({
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 1500,
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

    writeProjects(projects);

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
// UTILITIES
// ============================================================================

function logActivity(projectId, agent, action, status) {
  const logFile = path.join(STORAGE_DIR, "activity.log");
  const logEntry = { timestamp: new Date().toISOString(), projectId, agent, action, status };

  let logs = [];
  if (fs.existsSync(logFile)) {
    logs = JSON.parse(fs.readFileSync(logFile, "utf8"));
  }

  logs.push(logEntry);
  fs.writeFileSync(logFile, JSON.stringify(logs, null, 2));
}

// ============================================================================
// START SERVER
// ============================================================================

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`MAP Backend Server running on port ${PORT}`);
    console.log(`Anthropic API key: ${ANTHROPIC_API_KEY ? "configured" : "MISSING"}`);
    console.log(`Spec-kit agents dir: ${agentRegistry.SPEC_KIT_AGENTS_DIR}`);
  });
}

module.exports = app;
