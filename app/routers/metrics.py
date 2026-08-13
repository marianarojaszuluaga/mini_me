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

from app.core.security import authenticate_token
from app.services.metrics import collector

router = APIRouter(dependencies=[Depends(authenticate_token)])

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
async def agent_evaluations() -> list[dict[str, Any]]:
    return [
        _enrich(row, "agent_evaluation", agent_name=row.get("agent"))
        for row in collector.read_agent_evaluations()
    ]


@router.get("/metrics/reconciliation-runs")
async def reconciliation_runs() -> list[dict[str, Any]]:
    return [_enrich(row, "reconciliation_run") for row in collector.read_reconciliation_runs()]


@router.get("/metrics/usage-events")
async def usage_events() -> list[dict[str, Any]]:
    return [_enrich(row, "usage_event") for row in collector.read_usage_events()]


@router.get("/metrics/output-counts")
async def output_counts() -> list[dict[str, Any]]:
    return [_enrich(row, "output_count") for row in collector.read_output_counts()]


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
async def summary() -> dict[str, Any]:
    """One-shot payload for HU-010's analytics panel — all four series
    together, so the frontend doesn't need four round-trips."""
    return {
        "agentEvaluations": await agent_evaluations(),
        "reconciliationRuns": await reconciliation_runs(),
        "usageEvents": await usage_events(),
        "outputCounts": await output_counts(),
    }
