import React from "react";
import "./lifecycle.css";

// Ciclo de vida del proyecto (2026-08-24, Mariana: "Deberíamos tenerlo como
// un global... Es el MVP del Mini Me") — vista de portafolio: todos los
// proyectos activos, agrupados por su Project.currentPhase real, un
// Kanban de 5 columnas. No inventa datos nuevos: reusa GET /projects
// (currentPhase/currentStep ya reales) + GET /phases (títulos reales),
// ambos ya cargados por AppShell.
const PHASE_ACCENTS = {
  1: "var(--green)",
  2: "var(--blue)",
  3: "var(--blue)",
  4: "var(--amber)",
  5: "var(--text-3)"
};

export default function LifecycleView({ projects, phases, onOpenProject }) {
  const active = (projects || []).filter((p) => p.status !== "archived");
  const orderedPhases = [...(phases || [])].sort((a, b) => a.id - b.id);

  return (
    <div className="lifecycle-view">
      <div className="lifecycle-header">
        <h1>Ciclo de vida del proyecto</h1>
        <p>En qué fase real está cada proyecto activo, de un vistazo — la misma <code>Project.currentPhase</code> que ya se actualiza cada vez que se invoca un agente real.</p>
      </div>

      {orderedPhases.length === 0 ? (
        <div className="empty-state">Cargando fases...</div>
      ) : (
        <div className="lifecycle-board">
          {orderedPhases.map((phase) => {
            const projectsInPhase = active.filter((p) => (p.currentPhase || 1) === phase.id);
            return (
              <div key={phase.id} className="lifecycle-col">
                <div className="lifecycle-col-head" style={{ borderTopColor: PHASE_ACCENTS[phase.id] || "var(--border-strong)" }}>
                  <span className="lifecycle-col-num">{phase.id}</span>
                  <div>
                    <div className="lifecycle-col-title">{phase.title}</div>
                    <div className="lifecycle-col-count">{projectsInPhase.length} proyecto{projectsInPhase.length === 1 ? "" : "s"}</div>
                  </div>
                </div>
                <div className="lifecycle-col-body">
                  {projectsInPhase.length === 0 && <div className="lifecycle-empty">Sin proyectos acá</div>}
                  {projectsInPhase.map((project) => (
                    <button key={project.id} className="lifecycle-card" onClick={() => onOpenProject?.(project)}>
                      <div className="lifecycle-card-name">{project.name}</div>
                      <div className="lifecycle-card-step">{project.currentStep || "iniciando"}</div>
                    </button>
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
