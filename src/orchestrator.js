/**
 * MASTER ORCHESTRATOR
 *
 * Purpose: Coordinate all tools in the hybrid team system
 * - Routes requests to appropriate tool
 * - Chains tool outputs (tool1 output → tool2 input)
 * - Maintains global state
 * - Manages cross-tool workflows
 *
 * Tools managed:
 * - map: Project + agent orchestration (19 agents, 5 phases — see src/server.js)
 * - [Other tools]: Extensible architecture
 *
 * Usage (local):
 * npm install
 * node src/orchestrator.js
 *
 * Usage (Vercel): deployed via api/orchestrator.js, mounted under the
 * /orchestrator prefix — see the prefix-stripping middleware below. MAP_URL
 * must point at the deployed MAP service's public URL (e.g. .../map) —
 * `http://localhost:3001` only works when both run locally.
 */

const express = require("express");
const cors = require("cors");
require("dotenv").config();

const { authenticateToken } = require("./middleware/auth");
const store = require("./store");

const app = express();
const PORT = process.env.ORCHESTRATOR_PORT || 3000;
const MAP_URL = process.env.MAP_URL || `http://localhost:${process.env.PORT || 3001}`;

// On Vercel this app is reached via a rewrite from /orchestrator/(.*) to
// /api/orchestrator, but the request URL the function sees is still the
// original /orchestrator/... path — strip the prefix so routes below can
// stay mounted at root either way.
app.use((req, res, next) => {
  if (req.url === "/orchestrator" || req.url.startsWith("/orchestrator/")) {
    req.url = req.url.slice(13) || "/";
  }
  next();
});

app.use(cors());
app.use(express.json());

// ============================================================================
// TOOL REGISTRY - Extend this as you add tools
// ============================================================================

const toolRegistry = {
  map: {
    name: "MAP",
    description: "Multi-Agent Project Manager — 19 agents across 5 SDLC phases",
    url: MAP_URL,
    available: ["projects", "agents", "phases", "orchestrate", "evaluate"],
    inputs: ["projectId", "phase", "step"],
    outputs: ["project", "agentResult", "evaluation"]
  }
};

// Health check stays unauthenticated — see src/server.js for the same rationale.
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "orchestrator",
    timestamp: new Date().toISOString(),
    tools: Object.keys(toolRegistry)
  });
});

app.use(authenticateToken);

// ============================================================================
// REGISTRY
// ============================================================================

app.get("/tools", (req, res) => {
  res.json(Object.values(toolRegistry));
});

app.get("/tools/:name", (req, res) => {
  const tool = toolRegistry[req.params.name];
  if (!tool) return res.status(404).json({ error: "Tool not found" });
  res.json(tool);
});

// ============================================================================
// TOOL INVOCATION
// ============================================================================

async function callTool(toolName, action, body, token) {
  const tool = toolRegistry[toolName];
  if (!tool) {
    const err = new Error(`Tool not found: ${toolName}`);
    err.status = 404;
    throw err;
  }

  const response = await fetch(`${tool.url}/${action}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    throw new Error(`Tool ${toolName} failed: ${response.statusText}`);
  }

  return response.json();
}

app.post("/tools/:toolName/:action", async (req, res) => {
  try {
    const { toolName, action } = req.params;
    const result = await callTool(toolName, action, req.body, req.token);
    await store.logToolInvocation({
      timestamp: new Date().toISOString(),
      tool: toolName,
      action,
      status: "success"
    });
    res.json({ tool: toolName, action, timestamp: new Date().toISOString(), result });
  } catch (error) {
    res.status(error.status || 500).json({ error: error.message });
  }
});

// ============================================================================
// TOOLCHAIN EXECUTION - Chain multiple tools
// ============================================================================

// Shared by /toolchain/execute AND /workflows/:id/execute — no internal HTTP
// call to itself (that relied on `localhost`, which serverless invocations
// don't share).
async function executeToolchain(sequence, data, token) {
  if (!sequence || !Array.isArray(sequence)) {
    const err = new Error("sequence must be array of {tool, action}");
    err.status = 400;
    throw err;
  }

  let currentData = data || {};
  const results = [];

  for (const step of sequence) {
    const { tool, action } = step;
    const result = await callTool(tool, action, currentData, token);
    results.push({ tool, action, result });

    currentData = step.passOutput ? result : currentData;
    await store.logToolInvocation({
      timestamp: new Date().toISOString(),
      tool,
      action,
      status: "success"
    });
  }

  return { sequence, results, finalData: currentData, timestamp: new Date().toISOString() };
}

app.post("/toolchain/execute", async (req, res) => {
  try {
    const { sequence, data } = req.body;
    const result = await executeToolchain(sequence, data, req.token);
    res.json(result);
  } catch (error) {
    res.status(error.status || 500).json({ error: error.message });
  }
});

// ============================================================================
// WORKFLOWS - Save and execute tool sequences
// ============================================================================

app.get("/workflows", async (req, res) => {
  try {
    res.json(await store.readWorkflows());
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/workflows", async (req, res) => {
  try {
    const { name, description, sequence } = req.body;

    const workflow = {
      id: `workflow_${Date.now()}`,
      name,
      description,
      sequence,
      createdAt: new Date().toISOString()
    };

    const workflows = await store.readWorkflows();
    workflows.push(workflow);
    await store.writeWorkflows(workflows);

    res.status(201).json(workflow);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/workflows/:id/execute", async (req, res) => {
  try {
    const workflows = await store.readWorkflows();
    const workflow = workflows.find((w) => w.id === req.params.id);

    if (!workflow) {
      return res.status(404).json({ error: "Workflow not found" });
    }

    const execution = await executeToolchain(workflow.sequence, req.body.data || {}, req.token);
    res.json({ workflow: workflow.name, execution });
  } catch (error) {
    res.status(error.status || 500).json({ error: error.message });
  }
});

// ============================================================================
// SYSTEM STATE
// ============================================================================

app.get("/system/state", (req, res) => {
  res.json({
    tools: Object.keys(toolRegistry),
    port: PORT,
    storage: store.usingKV ? "vercel-kv" : "filesystem",
    timestamp: new Date().toISOString()
  });
});

// ============================================================================
// START (local/self-hosted only — Vercel requires the app, not a listener)
// ============================================================================

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Master Orchestrator running on port ${PORT}`);
    console.log(`Tools: ${Object.keys(toolRegistry).join(", ")}`);
    console.log(`MAP_URL: ${MAP_URL}`);
  });
}

module.exports = app;
