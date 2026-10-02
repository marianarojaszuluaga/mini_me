import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ProjectDetailDrillDown from "../ProjectDetail/ProjectDetailDrillDown.jsx";
import Modal from "../Modal/Modal.jsx";
import { AlertIcon } from "../icons.jsx";
import "./projects-view.css";

const NEW_PROJECT_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14M5 12h14" />
  </svg>
);

function NewProjectModal({ open, onClose, onCreate }) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [owner, setOwner] = useState("");
  // Campos opcionales (2026-09-28) — alimentan Secciones 1/3 del template de
  // Gaby (client/startDate/endDate) y Sección 2 (scopeAttachment), en vez de
  // quedar siempre vacíos o inventados por el agente.
  const [showOptional, setShowOptional] = useState(false);
  const [client, setClient] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [scopeAttachment, setScopeAttachment] = useState(null); // {filename, content}
  // workspacePath (2026-10-01) — lets reconciliation.py read this project's
  // own backlog/outputs folder instead of the single shared REPO_ROOT, so
  // two projects running in parallel never mix each other's evidence.
  const [workspacePath, setWorkspacePath] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleAttachmentChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) {
      setScopeAttachment(null);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setScopeAttachment({ filename: file.name, content: reader.result });
    reader.readAsText(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onCreate({
        name,
        description,
        owner: owner || t("projects.defaultOwner"),
        phase: 1,
        client: client || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        scopeAttachment: scopeAttachment || undefined,
        workspacePath: workspacePath || undefined
      });
      setName("");
      setDescription("");
      setOwner("");
      setClient("");
      setStartDate("");
      setEndDate("");
      setScopeAttachment(null);
      setWorkspacePath("");
      onClose();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <Modal open={open} onClose={onClose} title={t("projects.modal.title")} icon={NEW_PROJECT_ICON}>
      <form onSubmit={handleSubmit} className="pv-modal-form">
        <div>
          <label className="field-label">{t("projects.fields.name")}</label>
          <input
            className="field-input"
            type="text"
            placeholder={t("projects.fields.namePlaceholder")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="field-label">{t("projects.fields.description")}</label>
          <input
            className="field-input"
            type="text"
            placeholder={t("projects.fields.descriptionPlaceholder")}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="field-label">{t("projects.fields.owner")}</label>
          <input
            className="field-input"
            type="text"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
          />
        </div>
        <button type="button" className="btn-link pv-optional-toggle" onClick={() => setShowOptional((v) => !v)}>
          {showOptional ? t("projects.fields.hideOptional") : t("projects.fields.showOptional")}
        </button>
        {showOptional && (
          <>
            <div>
              <label className="field-label">{t("projects.fields.client")}</label>
              <input className="field-input" type="text" value={client} onChange={(e) => setClient(e.target.value)} />
            </div>
            <div className="pv-modal-form-row">
              <div>
                <label className="field-label">{t("projects.fields.startDate")}</label>
                <input className="field-input" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </div>
              <div>
                <label className="field-label">{t("projects.fields.endDate")}</label>
                <input className="field-input" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
            </div>
            <div>
              <label className="field-label">{t("projects.fields.scopeAttachment")}</label>
              <input className="field-input" type="file" accept=".md,.txt" onChange={handleAttachmentChange} />
              {scopeAttachment && <div className="pd-meta">{scopeAttachment.filename}</div>}
            </div>
            <div>
              <label className="field-label">{t("projects.fields.workspacePath")}</label>
              <input
                className="field-input"
                type="text"
                placeholder={t("projects.fields.workspacePathPlaceholder")}
                value={workspacePath}
                onChange={(e) => setWorkspacePath(e.target.value)}
              />
              <div className="pd-meta">{t("projects.fields.workspacePathHint")}</div>
            </div>
          </>
        )}
        <div className="modal-note modal-note-neutral">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 9v4M12 17h.01" />
            <circle cx="12" cy="12" r="9" />
          </svg>
          {t("projects.repoNote")}
        </div>
        {error && <div className="flag">{AlertIcon} {error}</div>}
        <div className="modal-actions">
          <button type="button" className="btn-cancel" onClick={onClose} disabled={busy}>
            {t("projects.actions.cancel")}
          </button>
          <button type="submit" className="btn-accent" disabled={busy || !name.trim()}>
            {busy ? t("projects.actions.creating") : t("projects.actions.create")}
          </button>
        </div>
      </form>
    </Modal>
  );
}

const SEMAPHORE_KEY = { "on-track": "onTrack", attention: "attention", blocked: "blocked" };

export default function ProjectsView({ api, agents, phases, initialProjectId, onInitialProjectConsumed }) {
  const { t } = useTranslation();
  const [projects, setProjects] = useState([]);
  const [gapsByProject, setGapsByProject] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedProject, setSelectedProject] = useState(null);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const projectList = await api.getProjects();
      setProjects(projectList);
      const entries = await Promise.all(
        projectList.map(async (project) => {
          try {
            const reconciliation = await api.getReconciliation(project.id);
            const gaps = Array.isArray(reconciliation) ? reconciliation : reconciliation?.gaps || [];
            return [project.id, gaps.filter((g) => g.status !== "cumple")];
          } catch {
            return [project.id, []];
          }
        })
      );
      setGapsByProject(Object.fromEntries(entries));
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  // Deep-link real desde la vista global "Ciclo de vida" (2026-08-24): abre
  // directo el proyecto que se clickeó ahí, en vez de forzar un segundo
  // click acá.
  useEffect(() => {
    if (!initialProjectId) return;
    api
      .getProject(initialProjectId)
      .then(setSelectedProject)
      .finally(() => onInitialProjectConsumed?.());
  }, [api, initialProjectId, onInitialProjectConsumed]);

  const handleCreate = async (data) => {
    await api.createProject(data);
    await load();
  };

  const handleSelect = async (projectId) => {
    const detail = await api.getProject(projectId);
    setSelectedProject(detail);
  };

  const semaphoreFor = (projectId) => {
    const count = (gapsByProject[projectId] || []).length;
    if (count >= 3) return "blocked";
    if (count >= 1) return "attention";
    return "on-track";
  };

  if (selectedProject) {
    return (
      <div className="pv-detail-wrap">
        <button className="pv-back-link" onClick={() => setSelectedProject(null)}>
          {t("projects.backLink")}
        </button>
        <ProjectDetailDrillDown
          api={api}
          project={selectedProject}
          agents={agents}
          phases={phases}
          onProjectUpdated={(fresh) => {
            setSelectedProject(fresh);
            load();
          }}
          onProjectArchived={() => {
            setSelectedProject(null);
            load();
          }}
        />
      </div>
    );
  }

  // Soft-deleted ("Eliminar proyecto") projects are archived, not removed —
  // real data stays, they just drop out of the active Proyectos grid.
  const visibleProjects = projects.filter((p) => p.status !== "archived");
  const blockedCount = visibleProjects.filter((p) => semaphoreFor(p.id) === "blocked").length;

  return (
    <div className="pv-view">
      <div className="pv-heading">
        <h1>{loading ? t("projects.heading.loading") : t("projects.heading.count", { count: visibleProjects.length })}</h1>
        {!loading && blockedCount > 0 && (
          <p className="pv-heading-sub">
            {t("projects.heading.blockedSub", { count: blockedCount })}
          </p>
        )}
      </div>

      {error && <div className="flag">{AlertIcon} {error}</div>}
      {loading ? (
        <div className="loading">{t("projects.loading")}</div>
      ) : visibleProjects.length === 0 ? (
        <div className="pv-empty-state">
          <div className="pv-empty-state-icon">{NEW_PROJECT_ICON}</div>
          <h2>{t("projects.empty.title")}</h2>
          <p>{t("projects.empty.body")}</p>
          <button className="btn-accent" onClick={() => setShowNewProjectModal(true)}>
            {t("projects.actions.new")}
          </button>
        </div>
      ) : (
        <div className="pv-grid">
          {visibleProjects.map((project) => {
            const brain = project.memory?.projectBrain || {};
            const semaphore = semaphoreFor(project.id);
            // DoD real de la fase actual (2026-09-26) — mismo dato que
            // alimenta project.progress en el backend, no un conteo aparte.
            const currentPhaseKey = phases?.find((p) => p.id === project.currentPhase)?.key;
            const currentChecklist = project.memory?.phaseChecklists?.[currentPhaseKey] || [];
            const dodDone = currentChecklist.filter((i) => i.done).length;
            return (
              <div key={project.id} className="pv-card" onClick={() => handleSelect(project.id)}>
                <div className="pv-card-top">
                  <div>
                    <div className="pv-card-name">{project.name}</div>
                    <div className="pv-card-phase">{t("projects.card.phase", { phase: project.currentPhase, step: project.currentStep || project.status })}</div>
                  </div>
                  <span className={`pv-pill pv-pill-${semaphore}`}>
                    <span className="pv-pill-dot" />
                    {t(`projects.semaphore.${SEMAPHORE_KEY[semaphore]}`)}
                  </span>
                </div>
                <div className="pv-card-stats">
                  <div className="pv-stat">
                    <span className="pv-stat-value">{(gapsByProject[project.id] || []).length}</span>
                    <span className="pv-stat-label">{t("projects.stats.gaps")}</span>
                  </div>
                  <div className="pv-stat">
                    <span className="pv-stat-value">{(brain.alerts || []).length}</span>
                    <span className="pv-stat-label">{t("projects.stats.alerts")}</span>
                  </div>
                  <div className="pv-stat">
                    <span className="pv-stat-value">{(brain.decisionLog || []).length}</span>
                    <span className="pv-stat-label">{t("projects.stats.decisions")}</span>
                  </div>
                  {currentChecklist.length > 0 && (
                    <div className="pv-stat">
                      <span className="pv-stat-value">{dodDone}/{currentChecklist.length}</span>
                      <span className="pv-stat-label">{t("projects.stats.dod")}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <button className="pv-card pv-card-new" onClick={() => setShowNewProjectModal(true)}>
            {t("projects.actions.new")}
          </button>
        </div>
      )}

      <NewProjectModal
        open={showNewProjectModal}
        onClose={() => setShowNewProjectModal(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}
