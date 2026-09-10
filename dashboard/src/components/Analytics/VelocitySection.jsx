import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

// Velocity/Speed/Rollover/Completion (Tarea 2, CTO QA/KPI 2026-09-10).
// Renders the "burndown de 3 líneas": planeado (committed_items),
// reportado (completed_items, manual PM input), y lo derivado de código
// (reconciliation gaps) — plus rollover and completion rate. See
// app/schemas/velocity.py for why completed_items must stay manual.
const VelocitySection = ({ api, projectId }) => {
  const { t } = useTranslation();
  const [state, setState] = useState({ loading: true, points: [], error: "" });

  useEffect(() => {
    let cancelled = false;
    if (!api || !projectId) {
      setState({ loading: false, points: [], error: "" });
      return;
    }
    (async () => {
      setState((s) => ({ ...s, loading: true, error: "" }));
      try {
        const series = await api.getVelocity(projectId);
        if (!cancelled) setState({ loading: false, points: series.points || [], error: "" });
      } catch (err) {
        if (!cancelled) setState({ loading: false, points: [], error: err.message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, projectId]);

  if (!projectId) return null;
  if (state.loading) return <div className="analytics-note">{t("analytics.velocity.loading")}</div>;
  if (state.error) {
    return <div className="analytics-note analytics-note-error">{t("analytics.velocity.error", { error: state.error })}</div>;
  }
  if (state.points.length === 0) {
    return <div className="analytics-note">{t("analytics.velocity.empty")}</div>;
  }

  const maxValue = Math.max(
    1,
    ...state.points.map((p) => Math.max(p.committed_items || 0, p.completed_items || 0, p.reconciliation_gaps_found || 0))
  );

  return (
    <div className="velocity-burndown">
      <div className="velocity-legend">
        <span className="velocity-legend-item"><i className="velocity-dot velocity-dot-planned" /> {t("analytics.velocity.planned")}</span>
        <span className="velocity-legend-item"><i className="velocity-dot velocity-dot-reported" /> {t("analytics.velocity.reported")}</span>
        <span className="velocity-legend-item"><i className="velocity-dot velocity-dot-derived" /> {t("analytics.velocity.derived")}</span>
      </div>
      <div className="velocity-rows">
        {state.points.map((point) => (
          <div key={point.week_start} className="velocity-row">
            <span className="velocity-week-label">{point.week_start}</span>
            <div className="velocity-bars">
              <div
                className="velocity-bar velocity-bar-planned"
                style={{ width: `${(100 * (point.committed_items || 0)) / maxValue}%` }}
                title={`${t("analytics.velocity.planned")}: ${point.committed_items}`}
              />
              <div
                className="velocity-bar velocity-bar-reported"
                style={{ width: `${(100 * (point.completed_items || 0)) / maxValue}%` }}
                title={`${t("analytics.velocity.reported")}: ${point.completed_items ?? "—"}`}
              />
              <div
                className="velocity-bar velocity-bar-derived"
                style={{ width: `${(100 * (point.reconciliation_gaps_found || 0)) / maxValue}%` }}
                title={`${t("analytics.velocity.derived")}: ${point.reconciliation_gaps_found ?? "—"}`}
              />
            </div>
            <span className="velocity-stats">
              {t("analytics.velocity.rollover")}: {point.rollover} · {t("analytics.velocity.completionRate")}:{" "}
              {point.completion_rate != null ? `${Math.round(point.completion_rate * 100)}%` : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default VelocitySection;
