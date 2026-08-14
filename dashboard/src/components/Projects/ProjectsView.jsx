import React, { useCallback, useEffect, useState } from "react";
import ProjectDetailDrillDown from "../ProjectDetail/ProjectDetailDrillDown.jsx";
import "./projects-view.css";

function NewProjectModal({ open, onClose, onCreate }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [owner, setOwner] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onCreate({ name, description, owner: owner || "sin asignar", phase: 1 });
      setName("");
      setDescription("");
      setOwner("");
      onClose();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <div className="pv-modal-backdrop" onClick={onClose}>
      <div className="pv-modal" onClick={(e) => e.stopPropagation()}>
        <div className="pv-modal-header">
          <h2>Nuevo proyecto</h2>
          <button type="button" className="btn-cancel" onClick={onClose}>
            Cerrar
          </button>
        </div>
        <form onSubmit={handleSubmit} className="pv-modal-form">
          <input
            type="text"
            placeholder="Nombre"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="Descripción"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="Asignado a (opcional)"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
          />
          <div className="pv-modal-note">
            El repositorio se conecta después, desde el detalle del proyecto — un repo siempre
            pertenece a un proyecto, nunca queda suelto.
          </div>
          {error && <div className="flag">⚠️ {error}</div>}
          <div className="modal-buttons">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={busy}>
              Cancelar
            </button>
            <button type="submit" className="btn-accent" disabled={busy || !name.trim()}>
              {busy ? "Creando..." : "Crear proyecto"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const SEMAPHORE_LABEL = { "on-track": "En curso", attention: "Atención", blocked: "Bloqueado" };

export default function ProjectsView({ api, agents, phases }) {
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
          ← Proyectos
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
        />
      </div>
    );
  }

  return (
    <div className="pv-view">
      <div className="pv-heading">
        <h1>{loading ? "Proyectos" : `${projects.length} proyectos`}</h1>
      </div>

      {error && <div className="flag">⚠️ {error}</div>}
      {loading ? (
        <div className="loading">Cargando proyectos...</div>
      ) : (
        <div className="pv-grid">
          {projects.map((project) => {
            const brain = project.memory?.projectBrain || {};
            const semaphore = semaphoreFor(project.id);
            return (
              <div key={project.id} className="pv-card" onClick={() => handleSelect(project.id)}>
                <div className="pv-card-top">
                  <div>
                    <div className="pv-card-name">{project.name}</div>
                    <div className="pv-card-phase">Fase {project.currentPhase} · {project.currentStep || project.status}</div>
                  </div>
                  <span className={`pv-pill pv-pill-${semaphore}`}>{SEMAPHORE_LABEL[semaphore]}</span>
                </div>
                <div className="pv-card-stats">
                  <div className="pv-stat">
                    <span className="pv-stat-value">{(gapsByProject[project.id] || []).length}</span>
                    <span className="pv-stat-label">Gaps</span>
                  </div>
                  <div className="pv-stat">
                    <span className="pv-stat-value">{(brain.alerts || []).length}</span>
                    <span className="pv-stat-label">Alertas</span>
                  </div>
                  <div className="pv-stat">
                    <span className="pv-stat-value">{(brain.decisionLog || []).length}</span>
                    <span className="pv-stat-label">Decisiones</span>
                  </div>
                </div>
              </div>
            );
          })}
          <button className="pv-card pv-card-new" onClick={() => setShowNewProjectModal(true)}>
            + Nuevo proyecto
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
