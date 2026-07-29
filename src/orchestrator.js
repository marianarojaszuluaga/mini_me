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
 * Usage:
 * npm install
 * node src/orchestrator.js
 */

const express = require("express");
const cors = require("cors");
require("dotenv").config();
const fs = require("fs");
const path = require("path");

const { authenticateToken } = require("./middleware/auth");

const app = express();
const PORT = process.env.ORCHESTRATOR_PORT || 3000;
const MAP_PORT = process.env.PORT || 3001;
const STORAGE_DIR = process.env.STORAGE_DIR || path.join(__dirname, "..", "storage");

app.use(cors());
app.use(express.json());

if (!fs.existsSync(STORAGE_DIR)) {
  fs.mkdirSync(STORAGE_DIR, { recursive: true });
}

// ============================================================================
// TOOL REGISTRY - Extend this as you add tools
// ============================================================================

const toolRegistry = {
  map: {
    name: "MAP",
    description: "Multi-Agent Project Manager — 19 agents across 5 SDLC phases",
    port: MAP_PORT,
    url: `http://localhost:${MAP_PORT}`,
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

app.post("/tools/:toolName/:action", async (req, res) => {
  try {
    const { toolName, action } = req.params;
    const tool = toolRegistry[toolName];

    if (!tool) {
      return res.status(404).json({ error: `Tool not found: ${toolName}` });
    }

    const toolUrl = `${tool.url}/${action}`;
    const response = await fetch(toolUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${req.token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(req.body)
    });

    if (!response.ok) {
      throw new Error(`Tool error: ${response.statusText}`);
    }

    const result = await response.json();
    logToolInvocation(toolName, action, result);

    res.json({
      tool: toolName,
      action,
      timestamp: new Date().toISOString(),
      result
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// TOOLCHAIN EXECUTION - Chain multiple tools
// ============================================================================

app.post("/toolchain/execute", async (req, res) => {
  try {
    const { sequence, data } = req.body;

    if (!sequence || !Array.isArray(sequence)) {
      return res.status(400).json({ error: "sequence must be array of {tool, action}" });
    }

    let currentData = data || {};
    const results = [];

    for (const step of sequence) {
      const { tool, action } = step;
      const toolObj = toolRegistry[tool];

      if (!toolObj) {
        throw new Error(`Tool not found: ${tool}`);
      }

      const toolUrl = `${toolObj.url}/${action}`;
      const response = await fetch(toolUrl, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${req.token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(currentData)
      });

      if (!response.ok) {
        throw new Error(`Tool ${tool} failed: ${response.statusText}`);
      }

      const result = await response.json();
      results.push({ tool, action, result });

      currentData = step.passOutput ? result : currentData;
      logToolInvocation(tool, action, result);
    }

    res.json({
      sequence,
      results,
      finalData: currentData,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// WORKFLOWS - Save and execute tool sequences
// ============================================================================

function workflowsFilePath() {
  return path.join(STORAGE_DIR, "workflows.json");
}

app.get("/workflows", (req, res) => {
  try {
    const file = workflowsFilePath();
    if (fs.existsSync(file)) {
      res.json(JSON.parse(fs.readFileSync(file, "utf8")));
    } else {
      res.json([]);
    }
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

    const file = workflowsFilePath();
    let workflows = [];
    if (fs.existsSync(file)) {
      workflows = JSON.parse(fs.readFileSync(file, "utf8"));
    }

    workflows.push(workflow);
    fs.writeFileSync(file, JSON.stringify(workflows, null, 2));

    res.status(201).json(workflow);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/workflows/:id/execute", async (req, res) => {
  try {
    const file = workflowsFilePath();
    const workflows = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : [];
    const workflow = workflows.find((w) => w.id === req.params.id);

    if (!workflow) {
      return res.status(404).json({ error: "Workflow not found" });
    }

    const response = await fetch(`http://localhost:${PORT}/toolchain/execute`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${req.token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        sequence: workflow.sequence,
        data: req.body.data || {}
      })
    });

    const result = await response.json();
    res.json({ workflow: workflow.name, execution: result });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// SYSTEM STATE
// ============================================================================

app.get("/system/state", (req, res) => {
  res.json({
    tools: Object.keys(toolRegistry),
    port: PORT,
    storage: STORAGE_DIR,
    timestamp: new Date().toISOString()
  });
});

// ============================================================================
// UTILITIES
// ============================================================================

function logToolInvocation(toolName, action, output) {
  const logFile = path.join(STORAGE_DIR, "orchestrator.log");
  const entry = { timestamp: new Date().toISOString(), tool: toolName, action, status: "success" };

  let logs = [];
  if (fs.existsSync(logFile)) {
    logs = JSON.parse(fs.readFileSync(logFile, "utf8"));
  }

  logs.push(entry);
  fs.writeFileSync(logFile, JSON.stringify(logs, null, 2));
}

// ============================================================================
// START
// ============================================================================

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Master Orchestrator running on port ${PORT}`);
    console.log(`Tools: ${Object.keys(toolRegistry).join(", ")}`);
  });
}

module.exports = app;
