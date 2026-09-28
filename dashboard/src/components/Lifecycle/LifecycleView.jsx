import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { BasecampCardsPanel } from "../ProjectDetail/BasecampCardsPanel.jsx";
import "./lifecycle.css";

// Real per-agent photos, same source AnalyticsDrillDown already uses (one
// file per agent id under assets/agent-avatars/*.jpg) — no new asset concept
// invented for this view.
const AGENT_PHOTOS = Object.fromEntries(
  Object.entries(import.meta.glob("../../assets/agent-avatars/*.jpg", { eager: true, import: "default" })).map(
    ([path, url]) => [path.match(/([^/]+)\.jpg$/)[1], url]
  )
);

// Ciclo de vida del proyecto (2026-08-24, Mariana: "Deberíamos tenerlo como
// un global... Es el MVP del Mini Me") — vista de portafolio: todos los
// proyectos activos, agrupados por su Project.currentPhase real, un
// Kanban de 5 columnas. No inventa datos nuevos: reusa GET /projects
// (currentPhase/currentStep/progress ya reales) + GET /phases (títulos y
// `agents` reales), ambos ya cargados por AppShell.
//
// TAREA B (2026-09-11): cada tarjeta se puede expandir a una "consola de
// fase" con las 7 piezas pedidas — progreso, acciones, asistente, correr
// agente con inputs, ver resultado + activar, registro en Project Brain y
// subir a repo. El click normal en la tarjeta sigue navegando a Proyectos
// (deep-link existente, onOpenProject/initialProjectId en AppShell) — la
// consola se abre con un botón aparte, para no romper ese flujo.
const PHASE_ACCENTS = {
  1: "var(--green)",
  2: "var(--blue)",
  3: "var(--blue)",
  4: "var(--amber)",
  5: "var(--text-3)"
};

function AgentAvatar({ agentId }) {
  const photo = AGENT_PHOTOS[agentId];
  return photo ? (
    <img className="avatar avatar-photo lifecycle-avatar" src={photo} alt={agentId} title={agentId} />
  ) : (
    <span className="avatar lifecycle-avatar" title={agentId}>
      {(agentId || "?").slice(0, 2).toUpperCase()}
    </span>
  );
}

function PhaseConsole({ api, project, phase, onProjectUpdated, t }) {
  const primaryAgent = phase.agents?.[0] || null;
  const [runningAgent, setRunningAgent] = useState(null); // agentId currently in the modal
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null); // { agent, output }
  const [activated, setActivated] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedPath, setUploadedPath] = useState(null);
  const [uploadedArtifactId, setUploadedArtifactId] = useState(null);
  const [showLinkedTasks, setShowLinkedTasks] = useState(false);

  // Gaps "contexto ciego" + "sin historial/feedback" (auditoría de flujos,
  // 2026-09-26): el context de Project Brain ahora lo agrega el backend
  // automáticamente (ver app/routers/agents.py::_with_brain_context), así
  // que acá solo falta (b) listar resultados previos y (c) permitir marcar
  // uno como "no sirvió" y reintentar con esa corrección como contexto.
  const [previousArtifacts, setPreviousArtifacts] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [correcting, setCorrecting] = useState(false);
  const [correctionNote, setCorrectionNote] = useState("");
  const [correctionOf, setCorrectionOf] = useState(null); // id del artefacto que se está corrigiendo

  // Real per-card Basecamp Card Table state, same data BasecampCardsPanel
  // already renders in Proyectos → Detalle. Only surfaced here (not built
  // twice) so running an agent and seeing the real tasks it maps to don't
  // require leaving the phase console — the gap flagged in the flow review
  // (2026-09-22) was that this already-real kanban was invisible from here,
  // not that it didn't exist. Hidden entirely (no toggle) when the project
  // has no Basecamp Card Table linked, so phases with nothing to show don't
  // grow an empty section.
  const hasLinkedCardTables = (project.basecamp?.selectedCardTableIds || []).length > 0;

  // DoD/checklist real de la fase (2026-09-26) — cada item viene 1:1 de los
  // `outputs` reales de esa fase (app/phases/phase_contracts.py), nunca
  // inventado aquí. `progress` en el proyecto ya se calcula desde esto en
  // el backend; togglear un item es la única forma real de moverlo.
  const checklist = project.memory?.phaseChecklists?.[phase.key] || [];
  const [checklistBusy, setChecklistBusy] = useState(null); // item id en vuelo

  const handleToggleChecklistItem = async (item) => {
    setChecklistBusy(item.id);
    setError("");
    try {
      await api.toggleChecklistItem(project.id, phase.key, item.id, !item.done);
      const fresh = await api.getProject(project.id);
      onProjectUpdated?.(fresh);
    } catch (err) {
      setError(err.message);
    }
    setChecklistBusy(null);
  };

  const brainStatus = project.memory?.projectBrain?.status;
  const isEmptyProject = brainStatus === "pending" && !(project.memory?.backlogs?.hu?.ids || []).length;

  const logBrainEvent = (type, content, metadata) =>
    api.ingestEvent(type, project.name, content, metadata).catch(() => {});

  const handleOpenAgent = (agentId) => {
    setRunningAgent(agentId);
    setInput("");
    setResult(null);
    setActivated(false);
    setUploadedPath(null);
    setUploadedArtifactId(null);
    setError("");
    setCorrecting(false);
    setCorrectionNote("");
    setCorrectionOf(null);
    setShowHistory(false);
    if (agentId && agentId !== "__project_brain__") {
      api
        .listPhaseArtifacts(project.id, phase.key)
        .then((list) => setPreviousArtifacts((list || []).filter((a) => a.agent === agentId)))
        .catch(() => setPreviousArtifacts([]));
    }
  };

  const handleViewPreviousArtifact = (artifact) => {
    setResult({ agent: artifact.agent, output: artifact.output });
    setActivated(artifact.status === "activated");
    setUploadedPath(artifact.repoPath || null);
    setUploadedArtifactId(artifact.id);
  };

  const handleRun = async () => {
    setBusy(true);
    setError("");
    try {
      const response = await api.invokeAgent(runningAgent, project.id, input, {
        phase: phase.key,
        source: "lifecycle",
        ...(correctionOf ? { previousArtifactId: correctionOf, correctionNote } : {})
      });
      setResult({ agent: runningAgent, output: response.output });
      setUploadedArtifactId(null);
      setUploadedPath(null);
      await logBrainEvent(
        "agent_invocation",
        `Se corrió el agente ${runningAgent} en la fase ${phase.key} del proyecto ${project.name}.`,
        { agent: runningAgent, phase: phase.key }
      );
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  const handleActivateProjectBrain = async (fields) => {
    setBusy(true);
    setError("");
    try {
      const content = `Nombre: ${fields.name}\nObjetivo: ${fields.objective}\nAlcance: ${fields.scope}`;
      await api.ingestEvent("project_brain_init", project.name, content, { phase: phase.key });
      const fresh = await api.getProject(project.id);
      onProjectUpdated?.(fresh);
      setRunningAgent(null);
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  const handleActivateResult = async () => {
    setActivated(true);
    await logBrainEvent(
      "agent_result_activated",
      `Resultado de ${result.agent} activado en la fase ${phase.key}: ${result.output.slice(0, 500)}`,
      { agent: result.agent, phase: phase.key }
    );
  };

  const handleUploadToRepo = async () => {
    setUploading(true);
    setError("");
    try {
      const filename = `${result.agent}-${Date.now()}.md`;
      const { path, artifactId } = await api.uploadPhaseArtifact(
        project.id,
        phase.key,
        filename,
        result.output,
        result.agent,
        input,
        correctionOf
      );
      setUploadedPath(path);
      setUploadedArtifactId(artifactId);
      await logBrainEvent("phase_artifact_uploaded", `Resultado de ${result.agent} subido a ${path}.`, {
        agent: result.agent,
        phase: phase.key,
        path
      });
    } catch (err) {
      setError(err.message);
    }
    setUploading(false);
  };

  // Gap "sin feedback/corrección": marca el resultado actual como "no
  // sirvió" y arma el siguiente run con el resultado anterior + la
  // corrección pedida como contexto, en vez de perderlo y arrancar de cero.
  const handleRejectResult = async () => {
    if (!correctionNote.trim()) return;
    setBusy(true);
    setError("");
    try {
      let artifactId = uploadedArtifactId;
      if (!artifactId) {
        const filename = `${result.agent}-${Date.now()}.md`;
        const uploaded = await api.uploadPhaseArtifact(
          project.id,
          phase.key,
          filename,
          result.output,
          result.agent,
          input,
          correctionOf,
          /* commitToRepo */ false
        );
        artifactId = uploaded.artifactId;
      }
      await api.submitArtifactFeedback(project.id, artifactId, correctionNote);
      setCorrectionOf(artifactId);
      setInput(`Resultado anterior:\n${result.output}\n\nCorrección pedida:\n${correctionNote}`);
      setResult(null);
      setActivated(false);
      setUploadedPath(null);
      setUploadedArtifactId(null);
      setCorrecting(false);
      setCorrectionNote("");
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <div className="lifecycle-console" onClick={(e) => e.stopPropagation()}>
      {/* 1. Indicador de progreso */}
      <div className="lifecycle-console-row">
        <strong>{phase.title}</strong>
        <span className="lifecycle-progress-pill">{project.progress ?? 0}%</span>
      </div>

      {/* 1b. DoD / checklist real de la fase */}
      {checklist.length > 0 && (
        <ul className="lifecycle-checklist">
          {checklist.map((item) => (
            <li key={item.id} className={item.done ? "done" : ""}>
              <label>
                <input
                  type="checkbox"
                  checked={!!item.done}
                  disabled={checklistBusy === item.id}
                  onChange={() => handleToggleChecklistItem(item)}
                />
                <span>{item.label}</span>
              </label>
              {item.done && item.evidence && <span className="lifecycle-checklist-evidence">{item.evidence}</span>}
            </li>
          ))}
        </ul>
      )}

      {/* 3. Asistente visible */}
      {primaryAgent && (
        <div className="lifecycle-console-row">
          <AgentAvatar agentId={primaryAgent} />
          <span>{t("lifecycle.console.mainAssistant", { agent: primaryAgent })}</span>
        </div>
      )}

      {/* 2. Acciones relevantes */}
      {isEmptyProject ? (
        <div className="lifecycle-brain-intro">
          <p>{t("lifecycle.console.brainExplainer")}</p>
          <button className="btn-secondary" onClick={() => handleOpenAgent("__project_brain__")}>
            {t("lifecycle.console.activateProjectBrain")}
          </button>
        </div>
      ) : (
        <div className="lifecycle-console-actions">
          {(phase.agents || []).map((agentId) => (
            <button key={agentId} className="btn-secondary" onClick={() => handleOpenAgent(agentId)}>
              <AgentAvatar agentId={agentId} /> {t("lifecycle.console.runAgent", { agent: agentId })}
            </button>
          ))}
        </div>
      )}

      {error && <div className="flag">{error}</div>}

      {/* 4. Correr agente con inputs / Project Brain flow */}
      {runningAgent === "__project_brain__" && (
        <ProjectBrainForm busy={busy} onCancel={() => setRunningAgent(null)} onSubmit={handleActivateProjectBrain} t={t} />
      )}
      {runningAgent && runningAgent !== "__project_brain__" && (
        <div className="lifecycle-console-form">
          {previousArtifacts.length > 0 && (
            <div className="lifecycle-artifact-history">
              <button className="btn-link" onClick={() => setShowHistory((v) => !v)}>
                {showHistory
                  ? t("lifecycle.console.hideHistory")
                  : t("lifecycle.console.showHistory", { count: previousArtifacts.length })}
              </button>
              {showHistory && (
                <ul className="lifecycle-artifact-history-list">
                  {previousArtifacts.map((artifact) => (
                    <li key={artifact.id}>
                      <span className={`lifecycle-artifact-status status-${artifact.status}`}>{artifact.status}</span>
                      <span className="lifecycle-artifact-date">{new Date(artifact.createdAt).toLocaleString()}</span>
                      <button className="btn-link" onClick={() => handleViewPreviousArtifact(artifact)}>
                        {t("lifecycle.console.viewResult")}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {correctionOf && <div className="lifecycle-correction-flag">↺ {t("lifecycle.console.retryingWithCorrection")}</div>}
          <textarea
            placeholder={t("lifecycle.console.inputPlaceholder")}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={3}
          />
          <div className="modal-buttons">
            <button className="btn-cancel" onClick={() => setRunningAgent(null)} disabled={busy}>
              {t("lifecycle.console.cancel")}
            </button>
            <button className="btn-primary" onClick={handleRun} disabled={busy || !input.trim()}>
              {busy ? t("lifecycle.console.running") : t("lifecycle.console.run")}
            </button>
          </div>
        </div>
      )}

      {/* 5. Ver resultados + activar después */}
      {result && (
        <div className="lifecycle-console-result">
          <div className="lifecycle-result-output">{result.output}</div>
          <div className="modal-buttons">
            <button className="btn-success" onClick={handleActivateResult} disabled={activated}>
              {activated ? t("lifecycle.console.activated") : t("lifecycle.console.activate")}
            </button>
            {/* 7. Subir al repo — solo después de activar */}
            {activated && (
              <button className="btn-secondary" onClick={handleUploadToRepo} disabled={uploading || !!uploadedPath}>
                {uploadedPath
                  ? t("lifecycle.console.uploaded")
                  : uploading
                  ? t("lifecycle.console.uploading")
                  : t("lifecycle.console.uploadToRepo")}
              </button>
            )}
            {/* Gap "sin feedback/corrección" (auditoría de flujos, 2026-09-26):
                marcar el resultado como no útil y reintentar con esa
                corrección como contexto, en vez de perderlo y arrancar de
                cero. No tiene sentido una vez ya se subió al repo. */}
            {!uploadedPath && (
              <button className="btn-cancel" onClick={() => setCorrecting((v) => !v)} disabled={busy}>
                {t("lifecycle.console.rejectResult")}
              </button>
            )}
          </div>
          {correcting && (
            <div className="lifecycle-console-form">
              <textarea
                placeholder={t("lifecycle.console.correctionPlaceholder")}
                value={correctionNote}
                onChange={(e) => setCorrectionNote(e.target.value)}
                rows={2}
              />
              <div className="modal-buttons">
                <button className="btn-cancel" onClick={() => setCorrecting(false)} disabled={busy}>
                  {t("lifecycle.console.cancel")}
                </button>
                <button className="btn-primary" onClick={handleRejectResult} disabled={busy || !correctionNote.trim()}>
                  {t("lifecycle.console.submitCorrection")}
                </button>
              </div>
            </div>
          )}
          {/* Confirmación explícita de qué pasó, no solo el cambio de label del
              botón — pedido de claridad de flujo (2026-09-11). */}
          {activated && (
            <div className="lifecycle-console-confirm">
              ✓ {t("lifecycle.console.activatedConfirm")}
            </div>
          )}
          {uploadedPath && (
            <div className="lifecycle-console-confirm">
              ✓ {t("lifecycle.console.uploadedConfirm", { path: uploadedPath })}
            </div>
          )}
        </div>
      )}

      {/* 6. Tareas reales vinculadas (Basecamp) — colapsado por defecto para
          no cambiar la altura/densidad habitual de la consola. */}
      {hasLinkedCardTables && (
        <div className="lifecycle-console-row lifecycle-linked-tasks">
          <button className="btn-link" onClick={() => setShowLinkedTasks((v) => !v)}>
            {showLinkedTasks ? t("lifecycle.console.hideLinkedTasks") : t("lifecycle.console.showLinkedTasks")}
          </button>
          {showLinkedTasks && (
            <div className="lifecycle-linked-tasks-panel">
              <BasecampCardsPanel api={api} project={project} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ProjectBrainForm({ busy, onCancel, onSubmit, t }) {
  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");
  const [scope, setScope] = useState("");

  return (
    <div className="lifecycle-console-form">
      <input placeholder={t("lifecycle.console.brainName")} value={name} onChange={(e) => setName(e.target.value)} />
      <textarea
        placeholder={t("lifecycle.console.brainObjective")}
        value={objective}
        onChange={(e) => setObjective(e.target.value)}
        rows={2}
      />
      <textarea
        placeholder={t("lifecycle.console.brainScope")}
        value={scope}
        onChange={(e) => setScope(e.target.value)}
        rows={2}
      />
      <div className="modal-buttons">
        <button className="btn-cancel" onClick={onCancel} disabled={busy}>
          {t("lifecycle.console.cancel")}
        </button>
        <button
          className="btn-primary"
          disabled={busy || !name.trim()}
          onClick={() => onSubmit({ name, objective, scope })}
        >
          {busy ? t("lifecycle.console.running") : t("lifecycle.console.activateProjectBrain")}
        </button>
      </div>
    </div>
  );
}

export default function LifecycleView({ api, agents, projects, phases, onOpenProject }) {
  const { t } = useTranslation();
  const active = (projects || []).filter((p) => p.status !== "archived");
  const orderedPhases = [...(phases || [])].sort((a, b) => a.id - b.id);
  const [expandedProjectId, setExpandedProjectId] = useState(null);
  const [liveProjects, setLiveProjects] = useState(active);

  React.useEffect(() => {
    setLiveProjects(active);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects]);

  const handleProjectUpdated = (fresh) => {
    setLiveProjects((prev) => prev.map((p) => (p.id === fresh.id ? fresh : p)));
  };

  return (
    <div className="lifecycle-view">
      <div className="lifecycle-header">
        <h1>{t("lifecycle.title")}</h1>
        <p>
          {t("lifecycle.subtitlePrefix")} <code>Project.currentPhase</code> {t("lifecycle.subtitleSuffix")}
        </p>
      </div>

      {orderedPhases.length === 0 ? (
        <div className="empty-state">{t("lifecycle.loadingPhases")}</div>
      ) : (
        <div className="lifecycle-board">
          {orderedPhases.map((phase) => {
            const projectsInPhase = liveProjects.filter((p) => (p.currentPhase || 1) === phase.id);
            const avgProgress = projectsInPhase.length
              ? Math.round(
                  projectsInPhase.reduce((sum, p) => sum + (p.progress ?? 0), 0) / projectsInPhase.length
                )
              : 0;
            return (
              <div key={phase.id} className="lifecycle-col">
                <div className="lifecycle-col-head" style={{ borderTopColor: PHASE_ACCENTS[phase.id] || "var(--border-strong)" }}>
                  <span className="lifecycle-col-num">{phase.id}</span>
                  <div>
                    <div className="lifecycle-col-title">{phase.title}</div>
                    <div className="lifecycle-col-count">
                      {t("lifecycle.projectCount", { count: projectsInPhase.length })}
                      {projectsInPhase.length > 0 && ` · ${avgProgress}%`}
                    </div>
                  </div>
                </div>
                <div className="lifecycle-col-body">
                  {projectsInPhase.length === 0 && <div className="lifecycle-empty">{t("lifecycle.noProjectsHere")}</div>}
                  {projectsInPhase.map((project) => (
                    <div key={project.id} className="lifecycle-card-wrap">
                      <button className="lifecycle-card" onClick={() => onOpenProject?.(project)}>
                        <div className="lifecycle-card-name">{project.name}</div>
                        <div className="lifecycle-card-step">{project.currentStep || t("lifecycle.startingStep")}</div>
                      </button>
                      <button
                        className="lifecycle-card-expand"
                        onClick={() => setExpandedProjectId(expandedProjectId === project.id ? null : project.id)}
                      >
                        {expandedProjectId === project.id ? t("lifecycle.console.collapse") : t("lifecycle.console.expand")}
                      </button>
                      {expandedProjectId === project.id && (
                        <PhaseConsole
                          api={api}
                          project={project}
                          phase={phase}
                          onProjectUpdated={handleProjectUpdated}
                          t={t}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
