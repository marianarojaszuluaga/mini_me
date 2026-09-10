"""
GET endpoints for the Analytics/Metrics layer (ARCHITECTURE_JARVIS.md §4/§7,
SPEC_JARVIS.md HU-008/009/010-JarvisMode). Write path is
services/metrics/collector.py, called from the routers/services that produce
each event (agent_evaluator, jarvis_chat, reconciliation); this router is the
read-only surface for the analytics panel.

HU-010 AC6 requires every aggregate number to carry a drill-down control to
the raw events that compose it ("Ninguna métrica se muestra sin poder hacer
drill-down a los eventos crudos que la componen"). Each of the four series
endpoints below therefore attaches an `eventIds` field per row, correlated
against the raw-event log added in services/metrics/collector.py
(_RAW_EVENTS_SERIES); GET /metrics/events?... is the endpoint that actually
resolves those ids back to full events. Aggregate rows written before this
change have no matching raw events (the raw log didn't exist yet) — those get
`eventIds: []` and `eventsAvailable: False` with an explicit note, per HU-010's
explicit "never fabricate a breakdown" AC.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.security import authenticate_api_key_or_user
from app.services.metrics import collector

router = APIRouter(dependencies=[Depends(authenticate_api_key_or_user)])

_NO_RAW_EVENTS_NOTE = (
    "sin eventos crudos disponibles, agregado antes de la capa de drill-down"
)


def _enrich(row: dict[str, Any], event_type: str, agent_name: str | None = None) -> dict[str, Any]:
    """Attaches eventIds/eventsAvailable (and an explicit note when there are
    none) to one aggregate row, by correlating it against the raw-event log
    on its own 'date' bucket ('YYYY-MM-DD')."""
    date_value = str(row.get("date", ""))
    date_bucket = date_value[:10]
    events = collector.events_for_bucket(event_type, date_bucket, agent_name=agent_name)

    # output-counts also needs to match on output `type` (several types share
    # a day), reconciliation-runs on project_id (several projects share a day).
    output_type = row.get("type")
    if event_type == "output_count" and output_type is not None:
        events = [event for event in events if event.get("payload", {}).get("type") == output_type]
    project_id = row.get("project_id")
    if event_type == "reconciliation_run" and project_id is not None:
        events = [event for event in events if event.get("payload", {}).get("project_id") == project_id]

    enriched = dict(row)
    enriched["eventIds"] = [event["id"] for event in events]
    enriched["eventsAvailable"] = bool(events)
    if not events:
        enriched["note"] = _NO_RAW_EVENTS_NOTE
    return enriched


@router.get("/metrics/agent-evaluations")
async def agent_evaluations(
    project_id: str | None = Query(default=None, description="Filter to one project's evaluations — omit for the system-wide (global) list"),
) -> list[dict[str, Any]]:
    rows = collector.read_agent_evaluations()
    if project_id is not None:
        rows = [row for row in rows if row.get("project_id") == project_id]
    return [_enrich(row, "agent_evaluation", agent_name=row.get("agent")) for row in rows]


@router.get("/metrics/reconciliation-runs")
async def reconciliation_runs() -> list[dict[str, Any]]:
    return [_enrich(row, "reconciliation_run") for row in collector.read_reconciliation_runs()]


@router.get("/metrics/usage-events")
async def usage_events() -> list[dict[str, Any]]:
    return [_enrich(row, "usage_event") for row in collector.read_usage_events()]


@router.get("/metrics/output-counts")
async def output_counts(
    project_id: str | None = Query(default=None, description="Filter to one project's outputs — omit for the system-wide total"),
) -> list[dict[str, Any]]:
    return [_enrich(row, "output_count") for row in collector.read_output_counts(project_id=project_id)]


@router.get("/metrics/events")
async def raw_events(
    type: str | None = Query(default=None, description="e.g. agent_evaluation, reconciliation_run, usage_event, output_count"),
    agent: str | None = Query(default=None),
    date_from: str | None = Query(default=None, description="ISO date/datetime, inclusive lower bound on timestamp"),
    date_to: str | None = Query(default=None, description="ISO date/datetime, inclusive upper bound on timestamp"),
) -> list[dict[str, Any]]:
    """Drill-down endpoint (HU-010 AC6): lists raw individual events, filterable
    by type/agent/date range. Every aggregate row from the four endpoints
    above carries eventIds that resolve into entries from this list."""
    return collector.read_raw_events(
        event_type=type,
        agent_name=agent,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/metrics/summary")
async def summary(
    project_id: str | None = Query(default=None, description="Scopes outputCounts/agentEvaluations/usageToday to one project too — the global slices stay present either way."),
) -> dict[str, Any]:
    """One-shot payload for HU-010's analytics panel — all four series
    together, so the frontend doesn't need four round-trips."""
    return {
        # Global agentEvaluations always included so P1's cross-project
        # legend keeps working; projectAgentEvaluations is the per-project
        # slice when a project is open (2026-08-21: "que quede visible
        # también a nivel proyecto" — both, never one instead of the other).
        "agentEvaluations": await agent_evaluations(),
        "projectAgentEvaluations": await agent_evaluations(project_id=project_id) if project_id else None,
        "reconciliationRuns": await reconciliation_runs(),
        "usageEvents": await usage_events(),
        "outputCounts": await output_counts(project_id=project_id),
        # Real "Uso hoy" rollup (Mariana, 2026-08-20: "uso hoy debe tener
        # fuente real") — never a fabricated/estimated number. Global always
        # present; projectUsageToday only when a project_id is given (global
        # Y por proyecto, 2026-08-21).
        "usageToday": collector.usage_today(),
        "projectUsageToday": collector.usage_today(project_id=project_id) if project_id else None,
    }
