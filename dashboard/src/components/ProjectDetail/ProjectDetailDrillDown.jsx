import React, { useEffect, useState } from "react";
import Modal from "../Modal/Modal.jsx";
import DestructiveActionModal from "../Modal/DestructiveActionModal.jsx";
import { AlertIcon, CheckIcon } from "../icons.jsx";
import { BasecampPublishSettings, SprintPublicationStatus } from "./BasecampPublishSettings.jsx";
import { BasecampCardsPanel } from "./BasecampCardsPanel.jsx";
import { BasecampNomenclatureRules } from "./BasecampNomenclatureRules.jsx";
import "../CommandCenter/command-center.css";

// Tarea 2 Gap 1 (2026-08-21) — nombre legible por proveedor real, usado en
// el selector de Auth Profile para distinguirlos de un vistazo.
const PROVIDER_LABEL = {
  github: "GitHub",
  bitbucket: "Bitbucket",
  basecamp: "Basecamp",
  google: "Google"
};

const REPO_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 2v4M15 2v4M6 10h12a1 1 0 011 1v3a5 5 0 01-5 5h-4a5 5 0 01-5-5v-3a1 1 0 011-1z" />
  </svg>
);

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
  { id: "fases", label: "Ciclo de vida del proyecto" },
  { id: "brain", label: "Project Brain" },
  { id: "repos", label: "Repositorios asociados" },
  { id: "basecamp", label: "Basecamp" },
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

// Tarea 1 (2026-08-21): picker "@" contextual — invoca un agente real
// directo desde su tag, sin que la usuaria tenga que abrir el chat ni
// recordar el id corto de memoria.
function AgentInvokeTag({ api, project, agent }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // { ok: bool, message: string } | null

  const handleInvoke = async () => {
    setBusy(true);
    setResult(null);
    try {
      const res = await api.invokeAgent(agent, project.id, `Corré tu verificación real para el proyecto ${project.name}.`, {
        trigger: "fases_y_agentes_tab",
      });
      setResult({ ok: true, message: (res.output || "").slice(0, 160) });
    } catch (err) {
      setResult({ ok: false, message: err.message });
    }
    setBusy(false);
  };

  return (
    <span className="agent-tag agent-tag-invokable">
      <span>{agent}</span>
      <button type="button" className="agent-tag-invoke" onClick={handleInvoke} disabled={busy} title={`Invocar a ${agent} para este proyecto`}>
        {busy ? "..." : "▶"}
      </button>
      {result && (
        <span className={`agent-tag-result ${result.ok ? "" : "agent-tag-result-error"}`}>
          {result.ok ? CheckIcon : AlertIcon} {result.message}
        </span>
      )}
    </span>
  );
}

function FasesYAgentesSection({ api, project, phases }) {
  if (!phases || phases.length === 0) {
    return <div className="empty-state">Cargando fases...</div>;
  }

  // Tarea 1: Front (Fase 3) y Back (Fase 2) no son un paso secuencial más —
  // arrancan en paralelo apenas Fase 1 entrega contratos, igual que un board
  // de Scrum real. Se agrupan en un mismo renglón en vez de una fila lineal.
  const phase1 = phases.find((p) => p.id === 1);
  const parallelPhases = phases.filter((p) => p.id === 2 || p.id === 3);
  const laterPhases = phases.filter((p) => p.id > 3);

  const renderPhase = (phase) => (
    <div key={phase.id} className={`phase-nav-item ${phase.id === project.currentPhase ? "active" : ""}`}>
      <div className="phase-nav-number">{phase.id}</div>
      <div className="phase-nav-content">
        <div className="phase-nav-title">{phase.title}</div>
        <div className="phase-nav-desc">{Array.isArray(phase.outputs) ? phase.outputs[0] : ""}</div>
      </div>
      <div className="phase-nav-agents">
        {phase.agents.length === 0 ? (
          <span className="agent-tag">sin agentes (tooling)</span>
        ) : (
          phase.agents.map((agent) => <AgentInvokeTag key={agent} api={api} project={project} agent={agent} />)
        )}
      </div>
    </div>
  );

  return (
    <div className="phases-list">
      {phase1 && renderPhase(phase1)}
      {parallelPhases.length > 0 && (
        <div className="phases-parallel-row">{parallelPhases.map(renderPhase)}</div>
      )}
      {laterPhases.map(renderPhase)}
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
      {reconciliation.note && <div className="flag">{AlertIcon} {reconciliation.note}</div>}
      {error && <div className="flag">{AlertIcon} {error}</div>}

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
              {/* BUG-019 fix (2026-08-21): la acción real que resuelve este estado, no solo el estado. */}
              {gap.helpText && <div className="recon-help-text">{AlertIcon} {gap.helpText}</div>}
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
  const [branches, setBranches] = useState(["main"]);
  const [branchDraft, setBranchDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Tarea 2 Gap 2 (2026-08-21): pull the account's real repos instead of
  // making the user type owner/repo by hand. `null` = loading,
  // `[]`/error = fall back to the manual text fields below.
  const [realRepos, setRealRepos] = useState(null);
  const [reposError, setReposError] = useState("");
  const [selectedRepoKey, setSelectedRepoKey] = useState("");
  const [manualMode, setManualMode] = useState(false);

  useEffect(() => {
    if (!authProfileId) return;
    setRealRepos(null);
    setReposError("");
    setSelectedRepoKey("");
    setManualMode(false);
    api
      .listAuthProfileRepos(authProfileId)
      .then((repos) => {
        setRealRepos(repos);
        if (repos.length === 0) setManualMode(true);
      })
      .catch((err) => {
        setReposError(err.message);
        setRealRepos([]);
        setManualMode(true);
      });
  }, [api, authProfileId]);

  const handleAuthProfileChange = (id) => {
    setAuthProfileId(id);
    const profile = authProfiles.find((p) => p.id === id);
    if (profile) setProvider(profile.provider);
  };

  const handleRepoPick = (key) => {
    setSelectedRepoKey(key);
    const picked = (realRepos || []).find((r) => `${r.owner}/${r.repo}` === key);
    if (picked) {
      setOwner(picked.owner);
      setRepo(picked.repo);
      if (picked.defaultBranch) setBranches([picked.defaultBranch]);
    }
  };

  const handleAddBranch = () => {
    const value = branchDraft.trim();
    if (!value || branches.includes(value)) return;
    setBranches((prev) => [...prev, value]);
    setBranchDraft("");
  };

  const handleRemoveBranch = (branch) => {
    setBranches((prev) => prev.filter((b) => b !== branch));
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
      // BUG (found 2026-08-14): this used to send `accessTokenRef`, but the
      // backend (app/routers/repositories.py) reads `auth_profile_id` — the
      // selected Auth Profile was silently ignored on every connect.
      await api.connectRepository(project.id, {
        provider,
        owner,
        repo,
        environment,
        auth_profile_id: authProfileId,
        branches
      });
      onConnected();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <Modal open onClose={onCancel} title="Conectar repositorio" icon={REPO_ICON}>
      <form onSubmit={handleSubmit} className="pd-connect-repo-form">
        <div>
          <label className="field-label">Auth Profile</label>
          <select className="field-select" value={authProfileId} onChange={(e) => handleAuthProfileChange(e.target.value)} required>
            {authProfiles.map((p) => (
              <option key={p.id} value={p.id}>
                {/* BUG-017 fix: label legible (cuenta — alcance), no el id crudo.
                    Tarea 2 Gap 1 (2026-08-21): prefijo de proveedor real para
                    distinguir GitHub personal/Imagine y Bitbucket de un
                    vistazo — un <option> nativo no puede llevar un ícono SVG. */}
                [{PROVIDER_LABEL[p.provider] || p.provider}] {p.account} — {p.scope ? p.scope : p.provider}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="field-label">Repositorio</label>
          {realRepos === null && <div className="loading">Cargando repos reales de la cuenta...</div>}
          {!manualMode && realRepos && realRepos.length > 0 && (
            <>
              <select
                className="field-select"
                value={selectedRepoKey}
                onChange={(e) => handleRepoPick(e.target.value)}
                required
              >
                <option value="" disabled>
                  Selecciona un repositorio
                </option>
                {realRepos.map((r) => (
                  <option key={`${r.owner}/${r.repo}`} value={`${r.owner}/${r.repo}`}>
                    {r.owner}/{r.repo}
                    {r.private ? " (privado)" : ""}
                    {r.language ? ` — ${r.language}` : ""}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn-link"
                style={{ marginTop: 6 }}
                onClick={() => setManualMode(true)}
              >
                Escribir owner/repo manualmente en su lugar
              </button>
            </>
          )}
          {manualMode && (
            <>
              {reposError && (
                <div className="flag" style={{ marginBottom: 8 }}>
                  {AlertIcon} No se pudo traer la lista real de repos ({reposError}). Escribí owner/repo a mano.
                </div>
              )}
              <input
                className="field-input"
                type="text"
                placeholder="owner"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                required
                style={{ marginBottom: 8 }}
              />
              <input
                className="field-input"
                type="text"
                placeholder="repo"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                required
              />
              {realRepos && realRepos.length > 0 && (
                <button type="button" className="btn-link" style={{ marginTop: 6 }} onClick={() => setManualMode(false)}>
                  Volver a elegir de la lista real
                </button>
              )}
            </>
          )}
        </div>
        <div>
          <label className="field-label">Ambiente</label>
          <select className="field-select" value={environment} onChange={(e) => setEnvironment(e.target.value)} required>
            <option value="" disabled>
              Environment (obligatorio)
            </option>
            <option value="prod">prod</option>
            <option value="develop">develop</option>
          </select>
        </div>

        <div className="pd-branches-field">
          <label className="field-label">Ramas a monitorear</label>
          <div className="pd-branches-list">
            {branches.map((b) => (
              <span key={b} className="branch-chip">
                {b}
                <button type="button" onClick={() => handleRemoveBranch(b)} aria-label={`Quitar ${b}`}>
                  ×
                </button>
              </span>
            ))}
          </div>
          <div className="pd-branches-add-row">
            <input
              className="field-input"
              type="text"
              placeholder="rama a monitorear (ej. develop)"
              value={branchDraft}
              onChange={(e) => setBranchDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddBranch();
                }
              }}
            />
            <button type="button" className="btn-secondary" onClick={handleAddBranch}>
              + Agregar
            </button>
          </div>
        </div>

        {error && <div className="flag">{AlertIcon} {error}</div>}
        <div className="modal-actions">
          <button type="button" className="btn-cancel" onClick={onCancel} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" className="btn-success" disabled={busy}>
            {busy ? "Conectando..." : "Conectar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function RepositoriosSection({ api, project, onProjectUpdated }) {
  const [repositories, setRepositories] = useState(project.repositories || []);
  const [authProfiles, setAuthProfiles] = useState(null); // null = not loaded yet
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [retryingId, setRetryingId] = useState(null);
  const [branchDrafts, setBranchDrafts] = useState({});
  const [scaffolding, setScaffolding] = useState(false);
  const [scaffoldResult, setScaffoldResult] = useState(null);

  const handleScaffold = async () => {
    setScaffolding(true);
    setScaffoldResult(null);
    setError("");
    try {
      const result = await api.scaffoldProject(project.id);
      setScaffoldResult(result);
    } catch (err) {
      setError(err.message);
    }
    setScaffolding(false);
  };

  const handleAddBranchToRepo = async (repoId) => {
    const value = (branchDrafts[repoId] || "").trim();
    if (!value) return;
    try {
      await api.addRepositoryBranch(project.id, repoId, value);
      const repos = await api.listProjectRepositories(project.id);
      setRepositories(repos);
      setBranchDrafts((prev) => ({ ...prev, [repoId]: "" }));
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    setRepositories(project.repositories || []);
  }, [project]);

  const handleRetry = async (repoId) => {
    setRetryingId(repoId);
    setError("");
    try {
      await api.retryRepositorySync(project.id, repoId);
      const repos = await api.listProjectRepositories(project.id);
      setRepositories(repos);
      const fresh = await api.getProject(project.id);
      onProjectUpdated?.(fresh);
    } catch (err) {
      setError(err.message);
    }
    setRetryingId(null);
  };

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
        <div style={{ display: "flex", gap: "8px" }}>
          {repositories.length > 0 && (
            <button className="btn-secondary" onClick={handleScaffold} disabled={scaffolding}>
              {scaffolding ? "Aplicando…" : "Aplicar estructura estándar"}
            </button>
          )}
          <button className="btn-primary" onClick={handleOpenForm}>
            {REPO_ICON}
            Agregar repositorio
          </button>
        </div>
      </div>

      {error && <div className="flag">{AlertIcon} {error}</div>}
      {scaffoldResult && (
        <div className="flag flag-success">
          {CheckIcon} Estructura aplicada en {scaffoldResult.repository.owner}/{scaffoldResult.repository.repo}:{" "}
          {scaffoldResult.filesWritten.join(", ")}
        </div>
      )}

      {repositories.length === 0 ? (
        <div className="pv-empty-cta-list">
          <div className="pv-eic-item">
            <div className="pv-eic-text">
              <strong>Sin repositorio conectado</strong>
              <span>La reconciliación no puede verificar código sin al menos un repo.</span>
            </div>
            <button className="btn-primary" onClick={handleOpenForm}>
              Integrar repo
            </button>
          </div>
        </div>
      ) : repositories.length === 0 ? null : (
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
              <div className="pd-branches-list">
                {(repo.branches || [repo.defaultBranch || "main"]).map((b) => (
                  <span key={b} className="branch-chip">
                    {b}
                  </span>
                ))}
              </div>
              <div className="pd-branches-add-row">
                <input
                  type="text"
                  placeholder="+ rama a monitorear"
                  value={branchDrafts[repo.id] || ""}
                  onChange={(e) => setBranchDrafts((prev) => ({ ...prev, [repo.id]: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddBranchToRepo(repo.id);
                    }
                  }}
                />
                <button type="button" className="btn-cancel" onClick={() => handleAddBranchToRepo(repo.id)}>
                  Agregar
                </button>
              </div>
              <div className="pd-meta">
                Última sincronización: {repo.lastSyncAt ? new Date(repo.lastSyncAt).toLocaleString() : "nunca"}
              </div>
              <div className="pd-meta pd-sync-status">
                {/* BUG-009: estado real (syncStatus/lastError vienen del backend,
                    nunca fabricados en el front) */}
                {repo.syncStatus === "error" ? (
                  <span className="pd-sync-status-row">
                    <span className="recon-status-pill recon-status-red">{AlertIcon} Error de sincronización</span>
                    {repo.lastError && <span className="pd-sync-error-detail">{repo.lastError}</span>}
                    <button
                      type="button"
                      className="btn-primary pd-retry-btn"
                      onClick={() => handleRetry(repo.id)}
                      disabled={retryingId === repo.id}
                    >
                      {retryingId === repo.id ? "Reintentando…" : "Reintentar"}
                    </button>
                  </span>
                ) : repo.syncStatus === "synced" ? (
                  <span className="recon-status-pill recon-status-green recon-status-pill-icon">
                    {CheckIcon} Sincronizado
                  </span>
                ) : (
                  <span className="recon-status-pill recon-status-amber">Sin sincronizar todavía</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && authProfiles !== null && authProfiles.length === 0 && (
        <div className="flag">
          {AlertIcon} No hay ningún Auth Profile creado todavía. Crea uno primero (sección de Auth Profiles)
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

  if (error) return <div className="flag">{AlertIcon} {error}</div>;
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
// Basecamp link — account_id + project_id, e.g. from
// https://3.basecamp.com/{account_id}/projects/{project_id}. Real link
// only: this does not read from the Basecamp API (that needs a connected
// Auth Profile's OAuth token) — just stores/shows the reference and a real
// "Ver en Basecamp" URL.
// ---------------------------------------------------------------------------

function BasecampSprintCard({ api, project }) {
  const [sprint, setSprint] = useState(null);
  const [sprintError, setSprintError] = useState("");

  useEffect(() => {
    api
      .getProjectSprint(project.id)
      .then(setSprint)
      .catch((err) => setSprintError(err.message));
  }, [api, project.id]);

  if (sprintError) {
    return <div className="pd-meta">Sprint (todolist, legacy): {sprintError}</div>;
  }
  if (!sprint) return null;

  const pct = sprint.tasks_total > 0 ? Math.round((sprint.tasks_done / sprint.tasks_total) * 100) : 0;

  return (
    <div className="sprint-card" style={{ marginTop: 12 }}>
      <div className="sprint-card-top">
        <span className="sprint-name">{sprint.name}</span>
      </div>
      <div className="sprint-bar">
        <div className="sprint-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="sprint-tasks">
        {sprint.tasks_done} de {sprint.tasks_total} tareas completadas
      </div>
    </div>
  );
}

// Tarea 2 Gap 3 (2026-08-21, corrección de Mariana): el espejo real viene de
// las Card Tables (columnas + cards), nunca del todolist — se muestra
// aparte del sprint legacy de arriba, que queda solo como referencia.
function BasecampMirrorCard({ api, project }) {
  const [mirror, setMirror] = useState(null);
  const [mirrorError, setMirrorError] = useState("");

  useEffect(() => {
    setMirror(null);
    setMirrorError("");
    api
      .getProjectBasecampMirror(project.id)
      .then(setMirror)
      .catch((err) => setMirrorError(err.message));
  }, [api, project.id]);

  if (mirrorError) {
    return (
      <div className="flag" style={{ marginTop: 12 }}>
        {AlertIcon} Espejo de Basecamp: {mirrorError}
      </div>
    );
  }
  if (!mirror) return <div className="loading">Cargando espejo real de Basecamp...</div>;

  return (
    <div className="basecamp-mirror-card" style={{ marginTop: 12 }}>
      <div className="basecamp-mirror-header">
        <strong>{mirror.name || project.name}</strong>
        {mirror.lastSyncAt && <span className="pd-meta">Última sync: {new Date(mirror.lastSyncAt).toLocaleString("es")}</span>}
      </div>
      {mirror.description && <p className="pd-meta">{mirror.description}</p>}
      {mirror.cardTables.length === 0 ? (
        <div className="empty-state">Sin Card Tables en el espejo todavía.</div>
      ) : (
        mirror.cardTables.map((table, i) => (
          <div key={i} className="basecamp-card-table">
            <div className="basecamp-card-table-name">{table.name}</div>
            <div className="basecamp-card-table-columns">
              {table.columns.map((col, j) => (
                <div key={j} className="basecamp-card-table-column">
                  <div className="basecamp-column-name">{col.name} ({col.cards.length})</div>
                  {col.cards.map((card, k) => (
                    <div key={k} className="basecamp-card">{card.title}</div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function BasecampLinkForm({ api, project, onLinked, onCancel }) {
  const [authProfiles, setAuthProfiles] = useState(null);
  const [authProfileId, setAuthProfileId] = useState("");
  const [bcProjects, setBcProjects] = useState(null);
  const [bcProjectsError, setBcProjectsError] = useState("");
  const [bcProjectId, setBcProjectId] = useState("");
  const [cardTables, setCardTables] = useState(null);
  const [cardTablesError, setCardTablesError] = useState("");
  const [selectedCardTableIds, setSelectedCardTableIds] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listAuthProfiles().then((profiles) => {
      const basecampProfiles = profiles.filter((p) => p.provider === "basecamp");
      setAuthProfiles(basecampProfiles);
      if (basecampProfiles[0]) setAuthProfileId(basecampProfiles[0].id);
    });
  }, [api]);

  useEffect(() => {
    if (!authProfileId) return;
    setBcProjects(null);
    setBcProjectsError("");
    api
      .listBasecampProjectsForProfile(authProfileId)
      .then(setBcProjects)
      .catch((err) => setBcProjectsError(err.message));
  }, [api, authProfileId]);

  const handlePickProject = async (id) => {
    setBcProjectId(id);
    setCardTables(null);
    setCardTablesError("");
    setSelectedCardTableIds([]);
    // Link primero (account_id real del profile elegido) para poder listar
    // sus Card Tables — un proyecto de Basecamp solo se puede leer con el
    // link real ya guardado.
    const profile = authProfiles.find((p) => p.id === authProfileId);
    const accountId = (profile?.scope || "").replace("account_id:", "");
    try {
      await api.linkBasecampProject(project.id, accountId, id);
      const tables = await api.listProjectCardTables(project.id);
      setCardTables(tables);
    } catch (err) {
      setCardTablesError(err.message);
      setCardTables([]);
    }
  };

  const toggleCardTable = (id) => {
    setSelectedCardTableIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.setProjectCardTables(project.id, selectedCardTableIds);
      onLinked();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <form onSubmit={handleSave} className="pd-connect-repo-form">
      <div>
        <label className="field-label">Auth Profile de Basecamp</label>
        {authProfiles === null && <div className="loading">Cargando Auth Profiles...</div>}
        {authProfiles && authProfiles.length === 0 && (
          <div className="flag">{AlertIcon} No hay ningún Auth Profile de Basecamp conectado todavía.</div>
        )}
        {authProfiles && authProfiles.length > 0 && (
          <select className="field-select" value={authProfileId} onChange={(e) => setAuthProfileId(e.target.value)}>
            {authProfiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.account}
              </option>
            ))}
          </select>
        )}
      </div>

      {authProfileId && (
        <div>
          <label className="field-label">Proyecto real de Basecamp</label>
          {bcProjectsError && <div className="flag">{AlertIcon} {bcProjectsError}</div>}
          {bcProjects === null && !bcProjectsError && <div className="loading">Cargando proyectos reales...</div>}
          {bcProjects && bcProjects.length > 0 && (
            <select className="field-select" value={bcProjectId} onChange={(e) => handlePickProject(e.target.value)} required>
              <option value="" disabled>Selecciona un proyecto</option>
              {bcProjects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
        </div>
      )}

      {bcProjectId && (
        <div>
          <label className="field-label">Card Table(s) — fuente real del "sprint actual"</label>
          {cardTablesError && <div className="flag">{AlertIcon} {cardTablesError}</div>}
          {cardTables === null && !cardTablesError && <div className="loading">Cargando Card Tables reales...</div>}
          {cardTables && cardTables.length === 0 && !cardTablesError && (
            <div className="empty-state">Este proyecto de Basecamp no tiene Card Tables.</div>
          )}
          {cardTables && cardTables.length > 0 && (
            <div className="basecamp-card-table-picker">
              {cardTables.map((t) => (
                <label key={t.id} className="basecamp-card-table-option">
                  <input
                    type="checkbox"
                    checked={selectedCardTableIds.includes(t.id)}
                    onChange={() => toggleCardTable(t.id)}
                  />
                  {t.title}
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <div className="flag">{AlertIcon} {error}</div>}
      <div className="modal-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="btn-success" disabled={busy || !bcProjectId}>
          {busy ? "Guardando..." : "Vincular"}
        </button>
      </div>
    </form>
  );
}

function BasecampSection({ api, project, onProjectUpdated }) {
  const existing = project.basecamp;
  const [showForm, setShowForm] = useState(false);

  const handleUnlink = async () => {
    const fresh = await api.unlinkBasecampProject(project.id);
    onProjectUpdated?.(fresh);
    setShowForm(false);
  };

  const handleLinked = async () => {
    const fresh = await api.getProject(project.id);
    onProjectUpdated?.(fresh);
    setShowForm(false);
  };

  const icon = (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 3h16a1 1 0 011 1v16a1 1 0 01-1 1H4a1 1 0 01-1-1V4a1 1 0 011-1z" />
    </svg>
  );

  return (
    <div className="pd-subsection">
      <div className="pd-subsection-header">
        <h3>Basecamp</h3>
        <button className="btn-primary" onClick={() => setShowForm(true)}>
          {existing ? "Editar" : "Vincular Basecamp"}
        </button>
      </div>

      {existing ? (
        <div className="pd-meta">
          Vinculado a{" "}
          <a
            href={`https://3.basecamp.com/${existing.account_id}/projects/${existing.project_id}`}
            target="_blank"
            rel="noreferrer"
          >
            https://3.basecamp.com/{existing.account_id}/projects/{existing.project_id}
          </a>{" "}
          <button type="button" className="btn-link" onClick={handleUnlink}>Desvincular</button>
          <BasecampMirrorCard api={api} project={project} />
          <BasecampSprintCard api={api} project={project} />
          <BasecampPublishSettings api={api} project={project} />
          {(existing.selectedCardTableIds || []).map((sprintId) => (
            <SprintPublicationStatus
              key={sprintId}
              api={api}
              project={project}
              sprintId={sprintId}
              publishEnabled={!!(existing.publish || {}).enabled}
            />
          ))}
          <BasecampCardsPanel api={api} project={project} />
          {(existing.selectedCardTableIds || []).length > 0 && (
            <BasecampNomenclatureRules
              api={api}
              accountId={existing.account_id}
              cardTables={existing.selectedCardTableIds.map((id) => ({
                key: `${existing.project_id}:${id}`,
                label: id,
              }))}
            />
          )}
        </div>
      ) : (
        <div className="pv-empty-cta-list">
          <div className="pv-eic-item">
            <div className="pv-eic-text">
              <strong>Sin Basecamp vinculado</strong>
              <span>Sin esto no se puede mostrar el espejo real del proyecto ni sus Card Tables.</span>
            </div>
            <button className="btn-primary" onClick={() => setShowForm(true)}>
              Integrar Basecamp
            </button>
          </div>
        </div>
      )}

      {showForm && (
        <Modal open onClose={() => setShowForm(false)} title="Vincular Basecamp" icon={icon}>
          <BasecampLinkForm api={api} project={project} onLinked={handleLinked} onCancel={() => setShowForm(false)} />
        </Modal>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const ARCHIVE_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 3h16a1 1 0 011 1v16a1 1 0 01-1 1H4a1 1 0 01-1-1V4a1 1 0 011-1zm3 5v9h2V8H7zm4 3v6h2v-6h-2zm4-2v8h2V9h-2z" />
  </svg>
);

export default function ProjectDetailDrillDown({ api, project, agents = [], phases = [], onProjectUpdated, onProjectArchived }) {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const [currentProject, setCurrentProject] = useState(project);
  const [showArchiveModal, setShowArchiveModal] = useState(false);

  useEffect(() => {
    setCurrentProject(project);
  }, [project]);

  const handleProjectUpdated = (fresh) => {
    setCurrentProject(fresh);
    onProjectUpdated?.(fresh);
  };

  const handleArchive = async () => {
    const fresh = await api.deleteProject(currentProject.id);
    setShowArchiveModal(false);
    onProjectArchived?.(fresh);
  };

  if (!currentProject) {
    return <div className="empty-state">Selecciona un proyecto para ver su detalle.</div>;
  }

  return (
    <div className="pd-drilldown">
      <div className="pd-header">
        <h2>{currentProject.name}</h2>
        <span className={`status-badge status-${currentProject.status}`}>{currentProject.status}</span>
        {currentProject.status !== "archived" && (
          <button className="btn-danger pd-archive-btn" onClick={() => setShowArchiveModal(true)}>
            Eliminar proyecto
          </button>
        )}
      </div>

      <DestructiveActionModal
        open={showArchiveModal}
        onClose={() => setShowArchiveModal(false)}
        title="Eliminar proyecto"
        icon={ARCHIVE_ICON}
        description={
          <>
            Vas a eliminar <strong>{currentProject.name}</strong> de la vista de Proyectos. No se
            borran sus datos — queda archivado y se puede recuperar. Sus repositorios/Basecamp
            vinculados dejan de sincronizarse mientras esté archivado.
          </>
        }
        verificationPhrase={currentProject.name}
        verificationLabel="nombre del proyecto"
        confirmLabel="Eliminar proyecto"
        bandText={`Eliminar ${currentProject.name} lo archiva y lo saca de la vista de Proyectos — puede recuperarse después, no borra datos.`}
        onConfirm={handleArchive}
      />

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
        {activeSection === "fases" && <FasesYAgentesSection api={api} project={currentProject} phases={phases} />}
        {activeSection === "brain" && (
          <ProjectBrainSection api={api} project={currentProject} onProjectUpdated={handleProjectUpdated} />
        )}
        {activeSection === "repos" && (
          <RepositoriosSection api={api} project={currentProject} onProjectUpdated={handleProjectUpdated} />
        )}
        {activeSection === "basecamp" && (
          <BasecampSection api={api} project={currentProject} onProjectUpdated={handleProjectUpdated} />
        )}
        {activeSection === "timeline" && <TimelineSection api={api} project={currentProject} />}
      </div>
    </div>
  );
}
