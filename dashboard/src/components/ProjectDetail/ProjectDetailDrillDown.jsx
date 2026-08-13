import React, { useEffect, useState } from "react";

/**
 * ProjectDetailDrillDown — "Detalle de Proyecto" (SPEC_JARVIS.md §2).
 *
 * Meant to be rendered as the `children` of the existing generic
 * <DrillDown> container (components/CommandCenter/DrillDown.jsx), e.g.:
 *
 *   <DrillDown open={open} onClose={close} label={`Detalle: ${project.name}`}>
 *     <ProjectDetailDrillDown api={api} project={project} agents={agents} />
 *   </DrillDown>
 *
 * Props:
 *  - api: ApiClient instance (see src/api-client.js)
 *  - project: the project record as returned by GET /projects/:id (includes
 *    memory.projectBrain, repositories[])
 *  - agents: full agents list, as returned by GET /agents (id, family) — same
 *    shape App.jsx already fetches at startup; passed down instead of
 *    re-fetched here to avoid an extra round trip.
 *  - phases: full phases list, as returned by GET /phases (id, title, agents[],
 *    outputs[]) — same as above.
 *  - onProjectUpdated?: (project) => void — called after an action that
 *    changes the project's server-side state (reconciliation run, repo
 *    connected), with the freshly-fetched project, so the parent can refresh
 *    its own copy too.
 */

const SECTIONS = [
  { id: "fases", label: "Fases y agentes" },
  { id: "brain", label: "Project Brain" },
  { id: "repos", label: "Repositorios asociados" },
  { id: "timeline", label: "Timeline de actividad" }
];

// ---------------------------------------------------------------------------
// Reconciliation status -> color mapping.
//
// Decision (own call, not spec'd verbatim): the backend
// (app/services/brain/reconciliation.py) currently emits four real statuses:
//   - "sin_test"              -> no test found linking to this AC yet
//   - "con_test_sin_resultado"-> test exists but no CI result is wired yet
//   - "no_reconciliable"      -> HU has no parseable AC checkboxes at all
//   - legacy "open"/"closed"  -> pre-HU-004 gap shape, kept for old data
//
// A true "cumple" (pass) and a hard "gap" (failing AC) are anticipated by the
// task brief and SPEC_JARVIS.md's HU-004 note ("cumple"/"no_cumple" once a CI
// result is available) but not yet producible by the backend — the module's
// own TODO says it never fabricates a pass/fail. This map is written to cover
// all of them now so the UI doesn't need another pass once CI lands:
//   cumple                 -> green   (verified pass)
//   sin_test                -> amber   (task brief: amber)
//   con_test_sin_resultado  -> amber   (task brief: amber — honest "not yet verifiable")
//   gap / no_cumple          -> red     (task brief: red)
//   no_reconciliable         -> gray    (neither pass nor fail — can't even be evaluated)
//   open (legacy)            -> red     (pre-HU-004 gap == unresolved == treated as gap)
//   closed (legacy)          -> green
const STATUS_STYLE = {
  cumple: { label: "Cumple", cls: "recon-status-green" },
  no_cumple: { label: "No cumple", cls: "recon-status-red" },
  gap: { label: "Gap", cls: "recon-status-red" },
  sin_test: { label: "Sin test", cls: "recon-status-amber" },
  con_test_sin_resultado: { label: "Con test, sin resultado", cls: "recon-status-amber" },
  no_reconciliable: { label: "No reconciliable", cls: "recon-status-gray" },
  open: { label: "Abierto (legacy)", cls: "recon-status-red" },
  closed: { label: "Cerrado (legacy)", cls: "recon-status-green" }
};

function StatusPill({ status }) {
  const style = STATUS_STYLE[status] || { label: status || "—", cls: "recon-status-gray" };
  return <span className={`recon-status-pill ${style.cls}`}>{style.label}</span>;
}

// ---------------------------------------------------------------------------
// 1. Fases y agentes
// ---------------------------------------------------------------------------

function FasesYAgentesSection({ project, phases }) {
  if (!phases || phases.length === 0) {
    return <div className="empty-state">Cargando fases...</div>;
  }

  return (
    <div className="phases-list">
      {phases.map((phase) => (
        <div
          key={phase.id}
          className={`phase-nav-item ${phase.id === project.currentPhase ? "active" : ""}`}
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
  );
}

// ---------------------------------------------------------------------------
// 2. Project Brain (Decision Log, Alerts, Reconciliacion)
// ---------------------------------------------------------------------------

function ReconciliationSubsection({ api, project, onProjectUpdated }) {
  const brain = project.memory?.projectBrain || {};
  const reconciliation = brain.reconciliation || { lastRunAt: null, gaps: [] };
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const handleRun = async () => {
    setRunning(true);
    setError("");
    try {
      await api.runReconciliation(project.id);
      const fresh = await api.getProject(project.id);
      onProjectUpdated?.(fresh);
    } catch (err) {
      setError(err.message);
    }
    setRunning(false);
  };

  return (
    <div className="pd-subsection">
      <div className="pd-subsection-header">
        <h3>Reconciliación</h3>
        <button className="btn-primary" onClick={handleRun} disabled={running}>
          {running ? "Reconciliando..." : "Reconciliar ahora"}
        </button>
      </div>

      {reconciliation.lastRunAt && (
        <div className="pd-meta">
          Última corrida: {new Date(reconciliation.lastRunAt).toLocaleString()}
        </div>
      )}
      {reconciliation.note && <div className="flag">⚠️ {reconciliation.note}</div>}
      {error && <div className="flag">⚠️ {error}</div>}

      {!reconciliation.gaps || reconciliation.gaps.length === 0 ? (
        <div className="empty-state">
          Sin resultados de reconciliación todavía. Corre "Reconciliar ahora".
        </div>
      ) : (
        <div className="evaluations-list">
          {reconciliation.gaps.map((gap, idx) => (
            <div key={gap.acceptanceCriterion ? `${gap.huId}-${idx}` : `${gap.huId}-noac-${idx}`} className="evaluation-item recon-item">
              <div className="eval-header">
                <span className="eval-agent">{gap.huId}</span>
                <StatusPill status={gap.status} />
              </div>
              {gap.acceptanceCriterion && <div className="recon-ac-text">{gap.acceptanceCriterion}</div>}
              {gap.reason && <div className="recon-ac-text recon-ac-reason">{gap.reason}</div>}
              {gap.testRef && <div className="pd-meta">Test: {gap.testRef}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectBrainSection({ api, project, onProjectUpdated }) {
  const brain = project.memory?.projectBrain || { decisionLog: [], alerts: [], meetingLog: [] };

  return (
    <div>
      <div className="pd-subsection">
        <h3>Decision Log ({brain.decisionLog.length})</h3>
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
      </div>

      <div className="pd-subsection">
        <h3>Alerts ({brain.alerts.length})</h3>
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

      <ReconciliationSubsection api={api} project={project} onProjectUpdated={onProjectUpdated} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Repositorios asociados
// ---------------------------------------------------------------------------

function ConnectRepoForm({ api, project, authProfiles, onConnected, onCancel }) {
  const [authProfileId, setAuthProfileId] = useState(authProfiles[0]?.id || "");
  const [provider, setProvider] = useState(authProfiles[0]?.provider || "github");
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [environment, setEnvironment] = useState(""); // no default, per task brief
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleAuthProfileChange = (id) => {
    setAuthProfileId(id);
    const profile = authProfiles.find((p) => p.id === id);
    if (profile) setProvider(profile.provider);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!environment) {
      setError("Selecciona un environment (prod o develop).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.connectRepository(project.id, {
        provider,
        owner,
        repo,
        environment,
        accessTokenRef: authProfileId
      });
      onConnected();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <form onSubmit={handleSubmit} className="pd-connect-repo-form">
      <select value={authProfileId} onChange={(e) => handleAuthProfileChange(e.target.value)} required>
        {authProfiles.map((p) => (
          <option key={p.id} value={p.id}>
            {/* BUG-017 fix: label legible (cuenta — alcance), no el id crudo */}
            {p.account} — {p.scope ? p.scope : p.provider}
          </option>
        ))}
      </select>
      <input
        type="text"
        placeholder="owner"
        value={owner}
        onChange={(e) => setOwner(e.target.value)}
        required
      />
      <input
        type="text"
        placeholder="repo"
        value={repo}
        onChange={(e) => setRepo(e.target.value)}
        required
      />
      <select value={environment} onChange={(e) => setEnvironment(e.target.value)} required>
        <option value="" disabled>
          Environment (obligatorio)
        </option>
        <option value="prod">prod</option>
        <option value="develop">develop</option>
      </select>
      {error && <div className="flag">⚠️ {error}</div>}
      <div className="modal-buttons">
        <button type="button" className="btn-cancel" onClick={onCancel} disabled={busy}>
          Cancelar
        </button>
        <button type="submit" className="btn-success" disabled={busy}>
          {busy ? "Conectando..." : "Conectar"}
        </button>
      </div>
    </form>
  );
}

function RepositoriosSection({ api, project, onProjectUpdated }) {
  const [repositories, setRepositories] = useState(project.repositories || []);
  const [authProfiles, setAuthProfiles] = useState(null); // null = not loaded yet
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setRepositories(project.repositories || []);
  }, [project]);

  const loadAuthProfiles = async () => {
    try {
      const profiles = await api.listAuthProfiles();
      setAuthProfiles(profiles);
    } catch (err) {
      setError(err.message);
      setAuthProfiles([]);
    }
  };

  const handleOpenForm = () => {
    setError("");
    setShowForm(true);
    if (authProfiles === null) loadAuthProfiles();
  };

  const handleConnected = async () => {
    setShowForm(false);
    try {
      const repos = await api.listProjectRepositories(project.id);
      setRepositories(repos);
      const fresh = await api.getProject(project.id);
      onProjectUpdated?.(fresh);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="pd-subsection">
      <div className="pd-subsection-header">
        <h3>Repositorios ({repositories.length})</h3>
        {!showForm && (
          <button className="btn-primary" onClick={handleOpenForm}>
            + Conectar repo
          </button>
        )}
      </div>

      {error && <div className="flag">⚠️ {error}</div>}

      {repositories.length === 0 ? (
        <div className="empty-state">Sin repositorios conectados todavía.</div>
      ) : (
        <div className="pd-repo-list">
          {repositories.map((repo) => (
            <div key={repo.id} className="pd-repo-item">
              <div className="pd-repo-main">
                <span className="agent-tag">{repo.provider}</span>
                <strong>
                  {repo.owner}/{repo.repo}
                </strong>
                <span className={`agent-tag ${repo.environment === "prod" ? "recon-status-red" : "recon-status-amber"}`}>
                  {repo.environment || "sin environment"}
                </span>
              </div>
              <div className="pd-meta">
                Última sincronización: {repo.lastSyncAt ? new Date(repo.lastSyncAt).toLocaleString() : "nunca"}
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && authProfiles !== null && authProfiles.length === 0 && (
        <div className="flag">
          ⚠️ No hay ningún Auth Profile creado todavía. Crea uno primero (sección de Auth Profiles)
          antes de poder conectar un repositorio.
          <div className="modal-buttons">
            <button type="button" className="btn-cancel" onClick={() => setShowForm(false)}>
              Cerrar
            </button>
          </div>
        </div>
      )}

      {showForm && authProfiles !== null && authProfiles.length > 0 && (
        <ConnectRepoForm
          api={api}
          project={project}
          authProfiles={authProfiles}
          onConnected={handleConnected}
          onCancel={() => setShowForm(false)}
        />
      )}

      {showForm && authProfiles === null && <div className="loading">Cargando Auth Profiles...</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. Timeline de actividad
// ---------------------------------------------------------------------------

function TimelineSection({ api, project }) {
  const [timeline, setTimeline] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.getTimeline(project.id);
        if (!cancelled) setTimeline(data);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, project.id]);

  if (error) return <div className="flag">⚠️ {error}</div>;
  if (timeline === null) return <div className="loading">Cargando timeline...</div>;

  const activities = timeline.activities || [];
  if (activities.length === 0) {
    return <div className="empty-state">Sin actividad registrada todavía.</div>;
  }

  // Cronológico: más reciente primero.
  const sorted = [...activities].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  return (
    <div className="evaluations-list">
      {sorted.map((activity, idx) => (
        <div key={idx} className="evaluation-item">
          <div className="eval-header">
            <span className="eval-agent">{activity.agent || "sistema"}</span>
            <span className="pd-meta">{new Date(activity.timestamp).toLocaleString()}</span>
          </div>
          <div>{activity.action}</div>
          <div className="pd-meta">{activity.status}</div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ProjectDetailDrillDown({ api, project, agents = [], phases = [], onProjectUpdated }) {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const [currentProject, setCurrentProject] = useState(project);

  useEffect(() => {
    setCurrentProject(project);
  }, [project]);

  const handleProjectUpdated = (fresh) => {
    setCurrentProject(fresh);
    onProjectUpdated?.(fresh);
  };

  if (!currentProject) {
    return <div className="empty-state">Selecciona un proyecto para ver su detalle.</div>;
  }

  return (
    <div className="pd-drilldown">
      <div className="pd-header">
        <h2>📁 {currentProject.name}</h2>
        <span className={`status-badge status-${currentProject.status}`}>{currentProject.status}</span>
      </div>

      <div className="pd-tabs">
        {SECTIONS.map((section) => (
          <button
            key={section.id}
            className={`pd-tab ${activeSection === section.id ? "active" : ""}`}
            onClick={() => setActiveSection(section.id)}
          >
            {section.label}
          </button>
        ))}
      </div>

      <div className="pd-tab-content">
        {activeSection === "fases" && <FasesYAgentesSection project={currentProject} phases={phases} />}
        {activeSection === "brain" && (
          <ProjectBrainSection api={api} project={currentProject} onProjectUpdated={handleProjectUpdated} />
        )}
        {activeSection === "repos" && (
          <RepositoriosSection api={api} project={currentProject} onProjectUpdated={handleProjectUpdated} />
        )}
        {activeSection === "timeline" && <TimelineSection api={api} project={currentProject} />}
      </div>
    </div>
  );
}
