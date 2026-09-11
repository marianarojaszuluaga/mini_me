import React, { useState } from "react";
import { useTranslation } from "react-i18next";
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
    setError("");
  };

  const handleRun = async () => {
    setBusy(true);
    setError("");
    try {
      const response = await api.invokeAgent(runningAgent, project.id, input, {
        phase: phase.key,
        source: "lifecycle"
      });
      setResult({ agent: runningAgent, output: response.output });
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
      const { path } = await api.uploadPhaseArtifact(project.id, phase.key, filename, result.output);
      setUploadedPath(path);
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

  return (
    <div className="lifecycle-console" onClick={(e) => e.stopPropagation()}>
      {/* 1. Indicador de progreso */}
      <div className="lifecycle-console-row">
        <strong>{phase.title}</strong>
        <span className="lifecycle-progress-pill">{project.progress ?? 0}%</span>
      </div>

      {/* 3. Asistente visible */}
      {primaryAgent && (
        <div className="lifecycle-console-row">
          <AgentAvatar agentId={primaryAgent} />
          <span>{t("lifecycle.console.mainAssistant", { agent: primaryAgent })}</span>
        </div>
      )}

      {/* 2. Acciones relevantes */}
      {isEmptyProject ? (
        <button className="btn-secondary" onClick={() => handleOpenAgent("__project_brain__")}>
          {t("lifecycle.console.activateProjectBrain")}
        </button>
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
                  ? t("lifecycle.console.uploaded", { path: uploadedPath })
                  : uploading
                  ? t("lifecycle.console.uploading")
                  : t("lifecycle.console.uploadToRepo")}
              </button>
            )}
          </div>
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
