/**
 * Orquestrador 360 — Dashboard
 *
 * Talks to the MAP server (src/server.js) via an app-issued API key (one of
 * APP_API_KEYS on the backend). This is NOT the Anthropic key — the backend
 * never accepts or forwards a raw Anthropic key from the browser, so there is
 * nothing sensitive to protect beyond a revocable app token.
 */

import React, { useState, useEffect } from "react";
import "./styles.css";

const STORAGE_KEY = "ORQ_APP_KEY";

class ApiClient {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.baseUrl = import.meta.env.VITE_API_URL || "http://localhost:3001";
  }

  async request(path, options = {}) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
        ...(options.headers || {})
      }
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || `${path} failed (${response.status})`);
    }
    return response.json();
  }

  getPhases() {
    return this.request("/phases");
  }

  getAgents() {
    return this.request("/agents");
  }

  getProjects() {
    return this.request("/projects");
  }

  getProject(id) {
    return this.request(`/projects/${id}`);
  }

  createProject(data) {
    return this.request("/projects", { method: "POST", body: JSON.stringify(data) });
  }

  invokeAgent(agentName, projectId, input, context) {
    return this.request(`/agents/${agentName}/invoke`, {
      method: "POST",
      body: JSON.stringify({ projectId, input, context })
    });
  }

  evaluate(agentName, output, context) {
    return this.request("/evaluate", {
      method: "POST",
      body: JSON.stringify({ agentName, output, context })
    });
  }
}

// ============================================================================
// COMPONENTS
// ============================================================================

const Header = () => (
  <div className="header">
    <div className="header-left">
      <h1>🎯 Orquestrador 360</h1>
      <p>19 agentes · 5 fases del SDLC</p>
    </div>
    <div className="header-right">
      <div className="status-badge">OPERATIONAL ✓</div>
    </div>
  </div>
);

const PhasesSidebar = ({ phases, selectedPhase, onPhaseSelect }) => (
  <div className="sidebar">
    <div className="sidebar-title">📊 Fases de Ejecución</div>
    <div className="phases-list">
      {phases.map((phase) => (
        <div
          key={phase.id}
          className={`phase-nav-item ${phase.id === selectedPhase ? "active" : ""}`}
          onClick={() => onPhaseSelect(phase.id)}
        >
          <div className="phase-nav-number">{phase.id}</div>
          <div className="phase-nav-content">
            <div className="phase-nav-title">{phase.title}</div>
            <div className="phase-nav-desc">
              {Array.isArray(phase.outputs) ? phase.outputs[0] : ""}
            </div>
          </div>
          <div className="phase-nav-agents">
            {phase.agents.length === 0 ? (
              <span className="agent-tag">sin agentes (tooling)</span>
            ) : (
              phase.agents.map((agent) => (
                <span key={agent} className="agent-tag">
                  {agent}
                </span>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  </div>
);

const ProjectsContent = ({ projects, onCreateProject, onSelectProject, loading }) => {
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ name: "", owner: "", description: "", phase: 1 });

  const handleCreateProject = async (e) => {
    e.preventDefault();
    try {
      await onCreateProject(formData);
      setShowModal(false);
      setFormData({ name: "", owner: "", description: "", phase: 1 });
    } catch (error) {
      alert("Error creando proyecto: " + error.message);
    }
  };

  return (
    <div className="projects-panel">
      <div className="panel-header">
        <h2>📁 Proyectos Activos</h2>
        <button className="btn-primary" onClick={() => setShowModal(true)}>
          + Nuevo Proyecto
        </button>
      </div>

      {loading ? (
        <div className="loading">Cargando proyectos...</div>
      ) : projects.length === 0 ? (
        <div className="empty-state">No hay proyectos. Crea uno nuevo para comenzar.</div>
      ) : (
        <div className="projects-grid">
          {projects.map((project) => (
            <div key={project.id} className="project-card" onClick={() => onSelectProject(project.id)}>
              <div className="project-header">
                <h3>{project.name}</h3>
                <span className={`status-badge status-${project.status}`}>{project.status}</span>
              </div>
              <div className="project-info">
                <span>👤 {project.owner}</span>
                <span>📊 Fase {project.currentPhase}</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${project.progress}%` }}></div>
              </div>
              <div className="project-progress-text">{project.progress}%</div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Crear Nuevo Proyecto</h2>
            <form onSubmit={handleCreateProject}>
              <input
                type="text"
                placeholder="Nombre del proyecto"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
              <input
                type="text"
                placeholder="Asignado a"
                value={formData.owner}
                onChange={(e) => setFormData({ ...formData, owner: e.target.value })}
                required
              />
              <input
                type="text"
                placeholder="Descripción"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                required
              />
              <select
                value={formData.phase}
                onChange={(e) => setFormData({ ...formData, phase: parseInt(e.target.value) })}
              >
                <option value={1}>Fase 1 - Planeación</option>
                <option value={2}>Fase 2 - Backend</option>
                <option value={3}>Fase 3 - Frontend</option>
                <option value={4}>Fase 4 - Integración y Calidad</option>
                <option value={5}>Fase 5 - Deploy</option>
              </select>
              <div className="modal-buttons">
                <button type="button" onClick={() => setShowModal(false)} className="btn-cancel">
                  Cancelar
                </button>
                <button type="submit" className="btn-success">
                  Crear
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

// Project Brain: decisions + alerts Gabriela extracted from actas
// (POST /brain/ingest-acta), plus the meeting log that fed them.
const BrainPanel = ({ project }) => {
  if (!project) {
    return (
      <div className="quality-panel">
        <h2>🧠 Project Brain</h2>
        <div className="empty-state">Selecciona un proyecto para ver su Brain.</div>
      </div>
    );
  }

  const brain = project.memory?.projectBrain || { decisionLog: [], alerts: [], meetingLog: [] };

  return (
    <div className="quality-panel">
      <h2>🧠 Project Brain — {project.name}</h2>

      <h3 style={{ marginTop: "10px" }}>Decision Log ({brain.decisionLog.length})</h3>
      {brain.decisionLog.length === 0 ? (
        <div className="empty-state">Sin decisiones registradas todavía.</div>
      ) : (
        <div className="evaluations-list">
          {brain.decisionLog.map((d, idx) => (
            <div key={idx} className="evaluation-item">
              <div className="eval-header">
                <span className="eval-agent">{d.decision}</span>
              </div>
              {d.context && <div>{d.context}</div>}
            </div>
          ))}
        </div>
      )}

      <h3 style={{ marginTop: "16px" }}>Alerts ({brain.alerts.length})</h3>
      {brain.alerts.length === 0 ? (
        <div className="empty-state">Sin alertas abiertas.</div>
      ) : (
        <div className="evaluations-list">
          {brain.alerts.map((a, idx) => (
            <div
              key={idx}
              className={`evaluation-item status-${a.severity === "HIGH" ? "critical" : a.severity === "MEDIUM" ? "warning" : "good"}`}
            >
              <div className="eval-header">
                <span className="eval-agent">{a.alert}</span>
                <span>{a.severity}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Invoke an agent directly, then optionally evaluate its output for real.
const AgentInvokePanel = ({ api, agents, projects, onEvaluated }) => {
  const [agentId, setAgentId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [input, setInput] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleInvoke = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const invokeResult = await api.invokeAgent(agentId, projectId || undefined, input, {
        invokedFrom: "dashboard"
      });
      setResult(invokeResult);
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  const handleEvaluate = async () => {
    if (!result) return;
    setBusy(true);
    setError("");
    try {
      const evaluation = await api.evaluate(agentId, result.output, { invokedFrom: "dashboard" });
      onEvaluated(evaluation);
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <div className="projects-panel">
      <div className="panel-header">
        <h2>⚙️ Invocar Agente</h2>
      </div>
      <form onSubmit={handleInvoke} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        <select value={agentId} onChange={(e) => setAgentId(e.target.value)} required>
          <option value="">Selecciona un agente</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.id} ({a.family})
            </option>
          ))}
        </select>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          <option value="">(sin proyecto asociado)</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <textarea
          placeholder="Input para el agente"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={3}
          required
        />
        <button type="submit" className="btn-primary" disabled={busy || !agentId}>
          {busy ? "Invocando..." : "Invocar"}
        </button>
      </form>

      {error && <div className="flag">⚠️ {error}</div>}

      {result && (
        <div style={{ marginTop: "15px" }}>
          <h3>Resultado</h3>
          <pre style={{ whiteSpace: "pre-wrap", maxHeight: "300px", overflow: "auto" }}>
            {result.output}
          </pre>
          <button className="btn-success" onClick={handleEvaluate} disabled={busy}>
            {busy ? "Evaluando..." : "Evaluar este output"}
          </button>
        </div>
      )}
    </div>
  );
};

const AgentStatus = ({ agents, evaluations }) => {
  const latestScoreFor = (agentId) => {
    const evalsForAgent = evaluations.filter((e) => e.agent === agentId);
    if (evalsForAgent.length === 0) return null;
    return evalsForAgent[evalsForAgent.length - 1];
  };

  return (
    <div className="agents-panel">
      <h2>🤖 Estado de Agentes ({agents.length})</h2>
      <div className="agents-grid">
        {agents.map((agent) => {
          const latest = latestScoreFor(agent.id);
          return (
            <div
              key={agent.id}
              className={`agent-card ${latest ? `status-${latest.status.toLowerCase()}` : ""}`}
            >
              <div className="agent-name">{agent.id}</div>
              <div className="agent-role">{agent.family}</div>
              <div className="agent-score">{latest ? `${latest.scores.overall}/100` : "sin evaluar"}</div>
              <div className="agent-status">{latest ? latest.status : "—"}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const QualityDashboard = ({ evaluations }) => (
  <div className="quality-panel">
    <h2>📈 Métricas de Calidad</h2>
    <div className="metrics-grid">
      <div className="metric-card">
        <div className="metric-value">
          {evaluations.length > 0
            ? Math.round(evaluations.reduce((acc, e) => acc + e.scores.overall, 0) / evaluations.length)
            : 0}
        </div>
        <div className="metric-label">Promedio General</div>
      </div>
      <div className="metric-card">
        <div className="metric-value">{evaluations.length}</div>
        <div className="metric-label">Evaluaciones</div>
      </div>
      <div className="metric-card">
        <div className="metric-value">{evaluations.filter((e) => e.status === "EXCELLENT").length}</div>
        <div className="metric-label">Excelentes</div>
      </div>
      <div className="metric-card">
        <div className="metric-value">
          {evaluations.filter((e) => e.status === "WARNING" || e.status === "CRITICAL").length}
        </div>
        <div className="metric-label">Alertas</div>
      </div>
    </div>

    {evaluations.length > 0 && (
      <div className="evaluations-list">
        {evaluations.map((evaluation, idx) => (
          <div key={idx} className={`evaluation-item status-${evaluation.status.toLowerCase()}`}>
            <div className="eval-header">
              <span className="eval-agent">{evaluation.agent}</span>
              <span className="eval-score">{evaluation.scores.overall}/100</span>
            </div>
            {evaluation.scores.redFlags.length > 0 && (
              <div className="eval-flags">
                {evaluation.scores.redFlags.map((flag, i) => (
                  <div key={i} className="flag">
                    ⚠️ {flag}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    )}
  </div>
);

// ============================================================================
// MAIN APP
// ============================================================================

export default function App() {
  const [appKey, setAppKey] = useState(localStorage.getItem(STORAGE_KEY) || "");
  const [authenticated, setAuthenticated] = useState(!!appKey);
  const [loading, setLoading] = useState(false);
  const [selectedPhase, setSelectedPhase] = useState(1);
  const [phases, setPhases] = useState([]);
  const [agents, setAgents] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProjectDetail, setSelectedProjectDetail] = useState(null);
  const [evaluations, setEvaluations] = useState([]);
  const [loginError, setLoginError] = useState("");

  const api = authenticated ? new ApiClient(appKey) : null;

  useEffect(() => {
    if (!authenticated || !api) return;
    (async () => {
      setLoading(true);
      try {
        const [phasesData, agentsData, projectsData] = await Promise.all([
          api.getPhases(),
          api.getAgents(),
          api.getProjects()
        ]);
        setPhases(phasesData);
        setAgents(agentsData);
        setProjects(projectsData);
      } catch (error) {
        console.error("Error loading initial data:", error);
        setLoginError(error.message);
        setAuthenticated(false);
        localStorage.removeItem(STORAGE_KEY);
      }
      setLoading(false);
    })();
  }, [authenticated]);

  const handleLogin = (e) => {
    e.preventDefault();
    localStorage.setItem(STORAGE_KEY, appKey);
    setLoginError("");
    setAuthenticated(true);
  };

  const handleCreateProject = async (projectData) => {
    const newProject = await api.createProject(projectData);
    setProjects([...projects, newProject]);
  };

  const handleEvaluated = (evaluation) => {
    setEvaluations((prev) => [...prev, evaluation]);
  };

  const handleSelectProject = async (projectId) => {
    try {
      const detail = await api.getProject(projectId);
      setSelectedProjectDetail(detail);
    } catch (error) {
      console.error("Error loading project detail:", error);
    }
  };

  if (!authenticated) {
    return (
      <div className="login-container">
        <div className="login-card">
          <h1>🎯 Orquestrador 360</h1>
          <p>Ingresa la App API Key (no tu clave de Anthropic)</p>
          <form onSubmit={handleLogin}>
            <input
              type="password"
              placeholder="App API Key"
              value={appKey}
              onChange={(e) => setAppKey(e.target.value)}
              required
            />
            <button type="submit">Iniciar Sesión</button>
          </form>
          {loginError && <div className="flag">⚠️ {loginError}</div>}
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <Header />
      <div className="main-layout">
        <PhasesSidebar phases={phases} selectedPhase={selectedPhase} onPhaseSelect={setSelectedPhase} />
        <div className="content">
          <div className="top-section">
            <ProjectsContent
              projects={projects}
              onCreateProject={handleCreateProject}
              onSelectProject={handleSelectProject}
              loading={loading}
            />
            <AgentInvokePanel api={api} agents={agents} projects={projects} onEvaluated={handleEvaluated} />
          </div>
          <div className="bottom-section">
            <AgentStatus agents={agents} evaluations={evaluations} />
            <QualityDashboard evaluations={evaluations} />
            <BrainPanel project={selectedProjectDetail} />
          </div>
        </div>
      </div>
    </div>
  );
}
