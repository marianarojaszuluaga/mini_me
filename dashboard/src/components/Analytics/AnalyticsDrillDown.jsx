import React, { useState, useEffect, useCallback } from "react";
import DrillDown from "../CommandCenter/DrillDown.jsx";
import ApiClient from "../../api-client.js";
import "./analytics.css";

const STORAGE_KEY = "ORQ_APP_KEY";

function defaultApi() {
  const key = localStorage.getItem(STORAGE_KEY);
  return key ? new ApiClient(key) : null;
}

// ----------------------------------------------------------------------------
// RawEventsPanel — resolves one aggregate row's eventIds back to the raw
// events that compose it (HU-010 AC6: "ningun numero sin poder hacer
// drill-down al evento crudo"). If eventsAvailable is false we show the
// backend's own note verbatim — never a fabricated breakdown.
// ----------------------------------------------------------------------------
const RawEventsPanel = ({ api, row, eventType }) => {
  const [state, setState] = useState({ loading: true, events: [], error: "" });

  useEffect(() => {
    let cancelled = false;
    if (!row.eventsAvailable) {
      setState({ loading: false, events: [], error: "" });
      return;
    }
    (async () => {
      try {
        const dateBucket = String(row.date || "").slice(0, 10);
        const filters = { type: eventType };
        if (row.agent) filters.agent = row.agent;
        if (dateBucket) {
          filters.date_from = dateBucket;
          filters.date_to = dateBucket;
        }
        const events = await api.getMetricsEvents(filters);
        const idSet = new Set(row.eventIds || []);
        const matched = events.filter((e) => idSet.has(e.id));
        if (!cancelled) setState({ loading: false, events: matched, error: "" });
      } catch (err) {
        if (!cancelled) setState({ loading: false, events: [], error: err.message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, row, eventType]);

  if (!row.eventsAvailable) {
    return <div className="analytics-note">{row.note || "sin eventos crudos disponibles"}</div>;
  }
  if (state.loading) return <div className="analytics-note">Cargando eventos...</div>;
  if (state.error) return <div className="analytics-note analytics-note-error">⚠️ {state.error}</div>;
  if (state.events.length === 0) {
    return <div className="analytics-note">Sin eventos crudos encontrados para este dato.</div>;
  }
  return (
    <div className="analytics-raw-events">
      {state.events.map((e) => (
        <pre key={e.id} className="analytics-raw-event">
          {JSON.stringify(e, null, 2)}
        </pre>
      ))}
    </div>
  );
};

// ----------------------------------------------------------------------------
// ExpandableMetric — one clickable number that expands into RawEventsPanel
// ----------------------------------------------------------------------------
const ExpandableMetric = ({ api, label, value, sublabel, row, eventType, accent }) => {
  const [expanded, setExpanded] = useState(false);
  const canExpand = !!row;

  return (
    <div className={`metric-tile${accent ? ` metric-tile-${accent}` : ""}`}>
      <button
        type="button"
        className="metric-tile-trigger"
        onClick={() => canExpand && setExpanded((v) => !v)}
        disabled={!canExpand}
        aria-expanded={expanded}
      >
        <div className="metric-tile-value">{value}</div>
        <div className="metric-tile-label">{label}</div>
        {sublabel && <div className="metric-tile-sublabel">{sublabel}</div>}
        {canExpand && <div className="metric-tile-hint">{expanded ? "ocultar eventos ▲" : "ver eventos crudos ▼"}</div>}
      </button>
      {expanded && canExpand && (
        <div className="metric-tile-detail">
          <RawEventsPanel api={api} row={row} eventType={eventType} />
        </div>
      )}
    </div>
  );
};

const Bar = ({ pct, colorVar }) => (
  <div className="bar-track">
    <div className="bar-fill" style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: colorVar }} />
  </div>
);

const AGENT_DIM_COLORS = {
  eficiencia: "var(--cat-blue)",
  acertividad: "var(--cat-green)",
  formato: "var(--cat-amber)",
  calidad: "var(--cat-purple)"
};

// ----------------------------------------------------------------------------
// Section blocks (P0 → P3, per SPEC_JARVIS.md §7)
// ----------------------------------------------------------------------------

const P0Section = ({ api, outputCounts, usageEvents, reconciliationRuns }) => {
  const byType = {};
  for (const row of outputCounts) {
    byType[row.type] = byType[row.type] || { count: 0, rows: [] };
    byType[row.type].count += row.count;
    byType[row.type].rows.push(row);
  }
  const totalInvocations = usageEvents.reduce((acc, r) => acc + (r.agent_invocations || 0), 0);
  const totalChatMessages = usageEvents.reduce((acc, r) => acc + (r.chat_messages || 0), 0);
  const gapsFound = reconciliationRuns.reduce((acc, r) => acc + (r.gaps_found || 0), 0);
  const gapsClosed = reconciliationRuns.reduce((acc, r) => acc + (r.gaps_closed_since_last || 0), 0);
  const lastUsage = usageEvents[usageEvents.length - 1];
  const lastRecon = reconciliationRuns[reconciliationRuns.length - 1];

  return (
    <section className="analytics-section analytics-section-p0">
      <h2 className="analytics-section-title">P0 — Lo esencial: ¿existe, se usa, encuentra desalineación real?</h2>

      <h3 className="analytics-subtitle">Outputs por tipo</h3>
      <div className="metric-grid">
        {Object.keys(byType).length === 0 && <div className="analytics-note">Sin outputs registrados todavía.</div>}
        {Object.entries(byType).map(([type, agg]) => (
          <ExpandableMetric
            key={type}
            api={api}
            label={type}
            value={agg.count}
            row={agg.rows[agg.rows.length - 1]}
            eventType="output_count"
          />
        ))}
      </div>

      <h3 className="analytics-subtitle">Número de usos</h3>
      <div className="metric-grid">
        <ExpandableMetric
          api={api}
          label="Invocaciones de agente (acumulado)"
          value={totalInvocations}
          row={lastUsage}
          eventType="usage_event"
        />
        <ExpandableMetric
          api={api}
          label="Mensajes de chat (acumulado)"
          value={totalChatMessages}
          row={lastUsage}
          eventType="usage_event"
        />
      </div>

      <h3 className="analytics-subtitle">Reconciliación — gaps encontrados vs. cerrados</h3>
      <div className="metric-grid">
        <ExpandableMetric
          api={api}
          label="Gaps encontrados (acumulado)"
          value={gapsFound}
          row={lastRecon}
          eventType="reconciliation_run"
          accent="red"
        />
        <ExpandableMetric
          api={api}
          label="Gaps cerrados desde la última corrida (acumulado)"
          value={gapsClosed}
          row={lastRecon}
          eventType="reconciliation_run"
          accent="green"
        />
      </div>
    </section>
  );
};

const P1Section = ({ api, agentEvaluations }) => {
  const byAgent = {};
  for (const row of agentEvaluations) {
    byAgent[row.agent] = byAgent[row.agent] || [];
    byAgent[row.agent].push(row);
  }

  return (
    <section className="analytics-section analytics-section-p1">
      <h2 className="analytics-section-title">P1 — Valor, no solo actividad</h2>

      <div className="analytics-note">
        Tasa de aceptación por tipo de output y costo por output (tokens/USD) todavía no tienen un
        evento correspondiente en el backend — no se muestra un número aquí para no inventar uno.
      </div>

      <h3 className="analytics-subtitle">Calidad en el tiempo por agente (4 dimensiones, HU-008)</h3>
      {Object.keys(byAgent).length === 0 && <div className="analytics-note">Sin evaluaciones registradas todavía.</div>}
      {Object.entries(byAgent).map(([agent, rows]) => {
        const last = rows[rows.length - 1];
        return (
          <div key={agent} className="agent-quality-card">
            <div className="agent-quality-header">
              <strong>{agent}</strong>
              <span className="analytics-note-inline">{rows.length} evaluaciones</span>
            </div>
            {["eficiencia", "acertividad", "formato", "calidad"].map((dim) => (
              <div key={dim} className="agent-quality-dim">
                <span className="agent-quality-dim-label">{dim}</span>
                <Bar pct={last[dim]} colorVar={AGENT_DIM_COLORS[dim]} />
                <span className="agent-quality-dim-value">{Math.round(last[dim])}</span>
              </div>
            ))}
            <ExpandableMetric
              api={api}
              label="ver evaluación cruda más reciente"
              value=""
              row={last}
              eventType="agent_evaluation"
            />
          </div>
        );
      })}
    </section>
  );
};

const weekKey = (dateStr) => {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "sin fecha";
  const onejan = new Date(d.getFullYear(), 0, 1);
  const week = Math.ceil(((d - onejan) / 86400000 + onejan.getDay() + 1) / 7);
  return `${d.getFullYear()}-W${String(week).padStart(2, "0")}`;
};

const P2Section = ({ changelog, outputCounts, reconciliationRuns }) => {
  const measured = changelog.filter((c) => c.after_scores);

  const weekly = {};
  for (const row of outputCounts) {
    const wk = weekKey(row.date);
    weekly[wk] = (weekly[wk] || 0) + row.count;
  }
  const weeks = Object.keys(weekly).sort();
  const maxWeekly = Math.max(1, ...Object.values(weekly));

  const byProject = {};
  for (const row of reconciliationRuns) {
    byProject[row.project_id] = (byProject[row.project_id] || 0) + row.gaps_found;
  }
  const maxProject = Math.max(1, ...Object.values(byProject));

  return (
    <section className="analytics-section analytics-section-p2">
      <h2 className="analytics-section-title">P2 — Contexto y tendencia</h2>

      <h3 className="analytics-subtitle">Antes vs. después (changelog de mejoras medido)</h3>
      {measured.length === 0 ? (
        <div className="analytics-note">
          Ninguna entrada del changelog tiene "después" medido todavía — se muestra "en progreso",
          no un número inventado.
        </div>
      ) : (
        measured.map((c) => (
          <div key={c.id} className="before-after-card">
            <strong>{c.agent_name}</strong> — {c.what_changed}
            <div className="before-after-grid">
              {["eficiencia", "acertividad", "formato", "calidad"].map((dim) => (
                <div key={dim} className="before-after-row">
                  <span>{dim}</span>
                  <span>{Math.round(c.before_scores[dim])} → {Math.round(c.after_scores[dim])}</span>
                </div>
              ))}
            </div>
          </div>
        ))
      )}

      <h3 className="analytics-subtitle">Tendencia semanal de outputs</h3>
      {weeks.length === 0 ? (
        <div className="analytics-note">Sin datos suficientes todavía.</div>
      ) : (
        <div className="weekly-trend">
          {weeks.map((wk) => (
            <div key={wk} className="weekly-trend-row">
              <span className="weekly-trend-label">{wk}</span>
              <Bar pct={(weekly[wk] / maxWeekly) * 100} colorVar="var(--cat-blue)" />
              <span className="weekly-trend-value">{weekly[wk]}</span>
            </div>
          ))}
        </div>
      )}

      <h3 className="analytics-subtitle">Distribución de gaps de reconciliación por proyecto</h3>
      {Object.keys(byProject).length === 0 ? (
        <div className="analytics-note">Sin corridas de reconciliación todavía.</div>
      ) : (
        <div className="weekly-trend">
          {Object.entries(byProject).map(([projectId, count]) => (
            <div key={projectId} className="weekly-trend-row">
              <span className="weekly-trend-label">{projectId}</span>
              <Bar pct={(count / maxProject) * 100} colorVar="var(--cat-purple)" />
              <span className="weekly-trend-value">{count}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

const P3Section = () => (
  <section className="analytics-section analytics-section-p3">
    <h2 className="analytics-section-title">P3 — Lo más blando</h2>
    <div className="analytics-note">
      Tiempo ahorrado estimado (aproximado, nunca medición exacta): el backend todavía no expone un
      evento de baseline vs. tiempo real de invocación para calcularlo — se omite en lugar de
      mostrar una estimación inventada.
    </div>
  </section>
);

const ChangelogSection = ({ api, changelog, onApprove }) => {
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");

  const handleApprove = async (id) => {
    setBusyId(id);
    setError("");
    try {
      const updated = await api.approveChangelogEntry(id);
      onApprove(updated);
    } catch (err) {
      setError(err.message);
    }
    setBusyId(null);
  };

  return (
    <section className="analytics-section analytics-section-changelog">
      <h2 className="analytics-section-title">Changelog de mejoras del sistema</h2>
      {error && <div className="analytics-note analytics-note-error">⚠️ {error}</div>}
      {changelog.length === 0 && <div className="analytics-note">Sin propuestas de mejora todavía.</div>}
      {changelog.map((entry) => (
        <div key={entry.id} className="changelog-entry">
          <div className="changelog-entry-header">
            <strong>{entry.agent_name}</strong>
            <span className={`changelog-status changelog-status-${entry.status}`}>{entry.status}</span>
          </div>
          <div className="changelog-entry-what">{entry.what_changed}</div>
          <div className="analytics-note-inline">Razón: {entry.reason}</div>
          {!entry.approved_at && (
            <button
              type="button"
              className="btn-primary"
              onClick={() => handleApprove(entry.id)}
              disabled={busyId === entry.id}
            >
              {busyId === entry.id ? "Aprobando..." : "Aprobar"}
            </button>
          )}
        </div>
      ))}
    </section>
  );
};

// ----------------------------------------------------------------------------
// AnalyticsDrillDown — top-level export
// ----------------------------------------------------------------------------
export default function AnalyticsDrillDown({ open, onClose, api: apiProp }) {
  const api = apiProp || defaultApi();
  const [data, setData] = useState(null);
  const [changelog, setChangelog] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!api) {
      setError("No hay App API Key configurada.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [summary, changelogData] = await Promise.all([api.getMetricsSummary(), api.listChangelog()]);
      setData(summary);
      setChangelog(changelogData);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  const handleApprove = (updated) => {
    setChangelog((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  };

  return (
    <DrillDown open={open} onClose={onClose} label="Analítica completa">
      <div className="analytics-drilldown">
        <div className="analytics-header">
          <h1>📈 Analítica completa</h1>
          <button type="button" className="btn-cancel" onClick={onClose}>
            Cerrar
          </button>
        </div>

        {loading && <div className="analytics-note">Cargando métricas...</div>}
        {error && <div className="analytics-note analytics-note-error">⚠️ {error}</div>}

        {data && (
          <>
            <P0Section
              api={api}
              outputCounts={data.outputCounts}
              usageEvents={data.usageEvents}
              reconciliationRuns={data.reconciliationRuns}
            />
            <P1Section api={api} agentEvaluations={data.agentEvaluations} />
            <P2Section
              changelog={changelog}
              outputCounts={data.outputCounts}
              reconciliationRuns={data.reconciliationRuns}
            />
            <P3Section />
            <ChangelogSection api={api} changelog={changelog} onApprove={handleApprove} />
          </>
        )}
      </div>
    </DrillDown>
  );
}
