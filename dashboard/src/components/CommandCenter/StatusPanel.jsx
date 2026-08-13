import React, { useState, useEffect, useCallback } from "react";
import ApiClient from "../../api-client.js";
import DrillDown from "./DrillDown.jsx";
import ProjectDetailDrillDown from "../ProjectDetail/ProjectDetailDrillDown.jsx";
import AnalyticsDrillDown from "../Analytics/AnalyticsDrillDown.jsx";
import MarMemoryDrillDown from "../MarMemory/MarMemoryDrillDown.jsx";
import IntegrationsDrillDown from "../Integrations/IntegrationsDrillDown.jsx";
import "./status-panel.css";

const STORAGE_KEY = "ORQ_APP_KEY";
const POLL_INTERVAL_MS = 30000;

/**
 * StatusPanel — Panel de Estado (SPEC_JARVIS.md §2).
 *
 * Shows:
 *  1. Semaforo por proyecto (on-track / atencion / bloqueado) based on open
 *     reconciliation gaps.
 *  2. Top 3 alertas de reconciliacion mas urgentes (cross projects + their
 *     reconciliation gaps).
 *  3. Snapshot de metricas clave (getMetricsSummary), shown as "big numbers".
 *  4. Click en un proyecto abre el DrillDown de "Detalle de Proyecto".
 *
 * Props:
 *  - refreshKey?: any — when this value changes, the panel refetches
 *    immediately (intended to be bumped by the chat when something relevant
 *    happens). Falls back to 30s polling when not supplied/used.
 *  - api? — ApiClient instance from App.jsx; falls back to building its own
 *    from the same ORQ_APP_KEY localStorage key if not supplied, so this
 *    component still works standalone.
 *  - agents?, phases? — full lists as returned by GET /agents, GET /phases,
 *    forwarded to the "Detalle de Proyecto" drill-down's "Fases y agentes"
 *    tab so it doesn't need to re-fetch them.
 */
export default function StatusPanel({ refreshKey, api: apiProp, agents = [], phases = [] }) {
  const [projects, setProjects] = useState([]);
  const [reconciliationByProject, setReconciliationByProject] = useState({});
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedProject, setSelectedProject] = useState(null);
  const [drillDownOpen, setDrillDownOpen] = useState(false);
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const [marMemoryOpen, setMarMemoryOpen] = useState(false);
  const [integrationsOpen, setIntegrationsOpen] = useState(false);

  const loadData = useCallback(async () => {
    const appKey = localStorage.getItem(STORAGE_KEY);
    const api = apiProp || (appKey ? new ApiClient(appKey) : null);
    if (!api) {
      setError("No hay sesion activa.");
      setLoading(false);
      return;
    }

    try {
      const [projectList, metricsSummary] = await Promise.all([
        api.getProjects(),
        api.getMetricsSummary()
      ]);

      const projectArray = Array.isArray(projectList) ? projectList : projectList?.projects || [];
      setProjects(projectArray);
      setMetrics(metricsSummary);

      // Cross projects with their reconciliation gaps. Fetched per-project
      // (no bulk endpoint) but only for the projects we actually have.
      const entries = await Promise.all(
        projectArray.map(async (project) => {
          try {
            const reconciliation = await api.getReconciliation(project.id);
            return [project.id, Array.isArray(reconciliation) ? reconciliation : reconciliation?.items || []];
          } catch {
            return [project.id, []];
          }
        })
      );
      setReconciliationByProject(Object.fromEntries(entries));
      setError("");
    } catch (err) {
      setError(err.message || "Error cargando estado.");
    } finally {
      setLoading(false);
    }
  }, [apiProp]);

  useEffect(() => {
    loadData();
  }, [loadData, refreshKey]);

  // TODO: reemplazar polling por invalidacion real cuando el chat dispare un evento
  useEffect(() => {
    const interval = setInterval(loadData, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [loadData]);

  const openProjectDrillDown = (project) => {
    setSelectedProject(project);
    setDrillDownOpen(true);
  };

  const getGaps = (projectId) =>
    (reconciliationByProject[projectId] || []).filter(
      (item) => item.status === "gap" || item.status === "no_reconciliable"
    );

  const getSemaphore = (projectId) => {
    const gapCount = getGaps(projectId).length;
    if (gapCount >= 3) return "blocked";
    if (gapCount >= 1) return "attention";
    return "on-track";
  };

  const semaphoreLabel = {
    "on-track": "En curso",
    attention: "Atencion",
    blocked: "Bloqueado"
  };

  // Top 3 alerts across all projects, most urgent first (blocked project
  // gaps first, then attention project gaps).
  const topAlerts = projects
    .flatMap((project) =>
      getGaps(project.id).map((gap) => ({
        project,
        gap,
        severity: getSemaphore(project.id) === "blocked" ? 0 : 1
      }))
    )
    .sort((a, b) => a.severity - b.severity)
    .slice(0, 3);

  if (loading) {
    return <div className="cc-panel-placeholder">Cargando estado...</div>;
  }

  if (error) {
    return <div className="cc-panel-placeholder status-panel-error">{error}</div>;
  }

  const appKey = localStorage.getItem(STORAGE_KEY);
  const api = apiProp || (appKey ? new ApiClient(appKey) : null);

  return (
    <div className="status-panel">
      <section className="status-panel-section">
        <div className="pd-subsection-header">
          <h3 className="status-panel-heading">Analitica e Integraciones</h3>
          <div className="modal-buttons status-panel-action-row">
            <button className="btn-primary" onClick={() => setAnalyticsOpen(true)}>
              📈 Analítica
            </button>
            <button className="btn-primary" onClick={() => setMarMemoryOpen(true)}>
              🧠 Memoria de Mar
            </button>
            <button className="btn-primary" onClick={() => setIntegrationsOpen(true)}>
              🔌 Integraciones
            </button>
          </div>
        </div>
      </section>

      <section className="status-panel-section">
        <h3 className="status-panel-heading">Metricas clave</h3>
        <div className="status-panel-metrics">
          <MetricTile label="Uso hoy" value={metrics?.usageToday ?? metrics?.usage_today ?? "-"} />
          <MetricTile label="Calidad reciente" value={metrics?.recentQuality ?? metrics?.recent_quality ?? "-"} />
          <MetricTile
            label="Gaps totales"
            value={Object.values(reconciliationByProject).reduce((sum, items) => sum + items.length, 0)}
          />
          <MetricTile label="Proyectos" value={projects.length} />
        </div>
      </section>

      <section className="status-panel-section">
        <h3 className="status-panel-heading">Alertas de reconciliacion</h3>
        {topAlerts.length === 0 ? (
          <p className="status-panel-empty">Sin alertas urgentes.</p>
        ) : (
          <ul className="status-panel-alerts">
            {topAlerts.map(({ project, gap }, idx) => (
              <li
                key={`${project.id}-${idx}`}
                className="status-panel-alert-item"
                onClick={() => openProjectDrillDown(project)}
              >
                <span className={`status-dot status-dot-${getSemaphore(project.id)}`} />
                <span className="status-panel-alert-text">
                  <strong>{project.name || project.id}</strong>: {gap.description || gap.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="status-panel-section">
        <h3 className="status-panel-heading">Proyectos</h3>
        <ul className="status-panel-projects">
          {projects.map((project) => {
            const semaphore = getSemaphore(project.id);
            return (
              <li
                key={project.id}
                className="status-panel-project-item"
                onClick={() => openProjectDrillDown(project)}
              >
                <span className={`status-dot status-dot-${semaphore}`} />
                <span className="status-panel-project-name">{project.name || project.id}</span>
                <span className={`status-panel-project-label status-panel-project-label-${semaphore}`}>
                  {semaphoreLabel[semaphore]}
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <DrillDown
        open={drillDownOpen}
        onClose={() => setDrillDownOpen(false)}
        label="Detalle de Proyecto"
      >
        {selectedProject && (
          <ProjectDetailDrillDown
            api={api}
            project={selectedProject}
            agents={agents}
            phases={phases}
            onProjectUpdated={(fresh) => {
              setSelectedProject(fresh);
              loadData();
            }}
          />
        )}
      </DrillDown>

      <AnalyticsDrillDown open={analyticsOpen} onClose={() => setAnalyticsOpen(false)} api={api} />
      <MarMemoryDrillDown open={marMemoryOpen} onClose={() => setMarMemoryOpen(false)} api={api} />
      <IntegrationsDrillDown
        open={integrationsOpen}
        onClose={() => setIntegrationsOpen(false)}
        api={api}
      />
    </div>
  );
}

function MetricTile({ label, value }) {
  return (
    <div className="status-panel-metric-tile">
      <div className="status-panel-metric-value">{value}</div>
      <div className="status-panel-metric-label">{label}</div>
    </div>
  );
}

function ProjectDetail({ project, gaps, semaphore, semaphoreLabel }) {
  return (
    <div className="status-panel-drilldown">
      <h2 className="status-panel-drilldown-title">{project.name || project.id}</h2>
      <p>
        <span className={`status-dot status-dot-${semaphore}`} /> {semaphoreLabel[semaphore]}
      </p>
      <h4>Gaps de reconciliacion ({gaps.length})</h4>
      {gaps.length === 0 ? (
        <p className="status-panel-empty">Sin gaps abiertos.</p>
      ) : (
        <ul>
          {gaps.map((gap, idx) => (
            <li key={idx}>{gap.description || `${gap.status} — ${gap.item || ""}`}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
