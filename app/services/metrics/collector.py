"""
Metrics collector — writes the time-series records defined in
app/schemas/metrics.py to storage. This is the single write path for the
Analytics layer (ARCHITECTURE_JARVIS.md §4, §7 / SPEC_JARVIS.md §7); readers
live in app/routers/metrics.py.

Series names (storage.py series/file names, one JSON list each):
- "metrics-agent-evaluations" -> list[AgentEvaluation]
- "metrics-reconciliation-runs" -> list[ReconciliationRun]
- "metrics-usage-events" -> list[UsageEvent]   (one entry per day, upserted)
- "metrics-output-counts" -> list[OutputCount] (one entry per type+project per day, upserted)
- "metrics-raw-events" -> list[RawMetricEvent] (one entry per individual event,
  written alongside the aggregates above — backs HU-010's drill-down requirement)
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.storage import get_storage
from app.schemas.metrics import (
    AgentEvaluation,
    OutputCount,
    OutputType,
    RawMetricEvent,
    ReconciliationRun,
    UsageEvent,
)

_AGENT_EVAL_SERIES = "metrics-agent-evaluations"
_RECONCILIATION_SERIES = "metrics-reconciliation-runs"
_USAGE_SERIES = "metrics-usage-events"
_OUTPUT_SERIES = "metrics-output-counts"

# Raw, per-event log backing HU-010's drill-down requirement (SPEC_JARVIS.md
# §HU-010 AC6). Kept as a *separate* append-only series from the four
# aggregates above — those stay untouched/as-fast-as-before for time-series
# dashboards; this one is only read by the drill-down endpoint
# (GET /metrics/events).
_RAW_EVENTS_SERIES = "metrics-raw-events"


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _record_raw_event(
    event_type: str,
    agent_name: str | None,
    payload: dict,
) -> RawMetricEvent:
    event = RawMetricEvent(type=event_type, agent_name=agent_name, payload=payload)
    storage = get_storage()
    storage.append_series(_RAW_EVENTS_SERIES, event.model_dump(mode="json"))
    return event


async def record_evaluation(
    agent_name: str,
    calidad: float,
    eficiencia: float,
    acertividad: float,
    formato: float,
) -> AgentEvaluation:
    """Appends one AgentEvaluation record — a raw, per-invocation data point.
    HU-009's changelog threshold (2 consecutive low-quality invocations,
    SPEC_JARVIS.md §10) is computed by reading this series, not here."""
    evaluation = AgentEvaluation(
        agent=agent_name,
        eficiencia=eficiencia,
        acertividad=acertividad,
        formato=formato,
        calidad=calidad,
        count=1,
    )
    storage = get_storage()
    storage.append_series(_AGENT_EVAL_SERIES, evaluation.model_dump(mode="json"))
    _record_raw_event(
        "agent_evaluation",
        agent_name,
        {
            "eficiencia": eficiencia,
            "acertividad": acertividad,
            "formato": formato,
            "calidad": calidad,
            "date": evaluation.date.isoformat(),
        },
    )
    return evaluation


async def record_output(
    output_type: OutputType,
    project_id: str | None = None,
    agent_name: str | None = None,
    count: int = 1,
) -> OutputCount:
    """Increments today's counter for a given output type, scoped to a
    project + agent when known — P0 metric, independent counter per
    (type, project_id, date) bucket, not just per type (2026-08-14: the
    Dashboard needs per-project output stats, not one global total).

    `count` lets one call record several outputs at once (e.g. N PRs found
    in a single repo digest) without N separate calls."""
    storage = get_storage()
    today = _today_iso()
    counts = storage.read_series(_OUTPUT_SERIES)

    for row in counts:
        if (
            row.get("type") == output_type
            and row.get("project_id") == project_id
            and row.get("date", "").startswith(today)
        ):
            row["count"] = row.get("count", 0) + count
            if agent_name and not row.get("agent_name"):
                row["agent_name"] = agent_name
            storage.write_series(_OUTPUT_SERIES, counts)
            _record_raw_event(
                "output_count",
                agent_name,
                {"type": output_type, "project_id": project_id, "date": today, "count": count},
            )
            return OutputCount(**row)

    record = OutputCount(type=output_type, count=count, project_id=project_id, agent_name=agent_name)
    counts.append(record.model_dump(mode="json"))
    storage.write_series(_OUTPUT_SERIES, counts)
    _record_raw_event(
        "output_count",
        agent_name,
        {"type": output_type, "project_id": project_id, "date": today, "count": count},
    )
    return record


async def record_usage_event(chat_message: bool = False, agent_invocation: bool = False) -> UsageEvent:
    """Increments today's usage rollup. Called once per chat turn
    (chat_message=True) and once per agent invocation triggered from that
    turn or from 'Invocar Agente' manual (agent_invocation=True) — a single
    call may set both to True."""
    storage = get_storage()
    today = _today_iso()
    events = storage.read_series(_USAGE_SERIES)

    for row in events:
        if row.get("date", "").startswith(today):
            if chat_message:
                row["chat_messages"] = row.get("chat_messages", 0) + 1
            if agent_invocation:
                row["agent_invocations"] = row.get("agent_invocations", 0) + 1
            storage.write_series(_USAGE_SERIES, events)
            _record_raw_event(
                "usage_event",
                None,
                {"chat_message": chat_message, "agent_invocation": agent_invocation, "date": today},
            )
            return UsageEvent(**row)

    record = UsageEvent(
        chat_messages=1 if chat_message else 0,
        agent_invocations=1 if agent_invocation else 0,
    )
    events.append(record.model_dump(mode="json"))
    storage.write_series(_USAGE_SERIES, events)
    _record_raw_event(
        "usage_event",
        None,
        {"chat_message": chat_message, "agent_invocation": agent_invocation, "date": today},
    )
    return record


async def record_reconciliation_run(
    project_id: str,
    gaps_found: int,
    gaps_closed_since_last: int,
    sin_test: int,
) -> ReconciliationRun:
    """Appends one reconciliation run — called by
    services/brain/reconciliation.py at the end of its pass (§5)."""
    run = ReconciliationRun(
        project_id=project_id,
        gaps_found=gaps_found,
        gaps_closed_since_last=gaps_closed_since_last,
        sin_test=sin_test,
    )
    storage = get_storage()
    storage.append_series(_RECONCILIATION_SERIES, run.model_dump(mode="json"))
    _record_raw_event(
        "reconciliation_run",
        None,
        {
            "project_id": project_id,
            "gaps_found": gaps_found,
            "gaps_closed_since_last": gaps_closed_since_last,
            "sin_test": sin_test,
            "date": run.date.isoformat(),
        },
    )
    return run


# -- read helpers, shared with routers/metrics.py ---------------------------
# Kept here (not duplicated in the router) since both evaluate_invocation.py's
# "2 consecutive low quality" check (HU-009) and the router need them.

def read_agent_evaluations() -> list[dict]:
    return get_storage().read_series(_AGENT_EVAL_SERIES)


def read_reconciliation_runs() -> list[dict]:
    return get_storage().read_series(_RECONCILIATION_SERIES)


def read_usage_events() -> list[dict]:
    return get_storage().read_series(_USAGE_SERIES)


def read_output_counts(project_id: str | None = None) -> list[dict]:
    counts = get_storage().read_series(_OUTPUT_SERIES)
    if project_id is not None:
        counts = [row for row in counts if row.get("project_id") == project_id]
    return counts


def read_raw_events(
    event_type: str | None = None,
    agent_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """Reads the raw-event drill-down log (HU-010 AC6), optionally filtered.
    date_from/date_to are ISO date or datetime strings, compared
    lexicographically against each event's ISO timestamp (works for both
    'YYYY-MM-DD' and full 'YYYY-MM-DDTHH:MM:SS' since ISO 8601 sorts as text).
    """
    events = get_storage().read_series(_RAW_EVENTS_SERIES)

    if event_type:
        events = [event for event in events if event.get("type") == event_type]
    if agent_name:
        events = [event for event in events if event.get("agent_name") == agent_name]
    if date_from:
        events = [event for event in events if event.get("timestamp", "") >= date_from]
    if date_to:
        # BUG-013 fix: a bare date (e.g. "2026-08-13") sorts *before* any
        # full ISO timestamp on that same day ("2026-08-13T10:00:00Z"), so
        # the naive lexicographic "<=" excluded every event from the
        # end-date itself. Extend a date-only date_to to the end of that
        # day before comparing; a full timestamp is used as-is.
        effective_date_to = date_to if "T" in date_to else f"{date_to}T23:59:59.999999Z"
        events = [event for event in events if event.get("timestamp", "") <= effective_date_to]

    return events


def events_for_bucket(
    event_type: str,
    date_bucket: str,
    agent_name: str | None = None,
) -> list[dict]:
    """Correlates one aggregate point (e.g. one AgentEvaluation day-row) back
    to the raw events that compose it, matching on type + the event's own
    'date' payload field (a 'YYYY-MM-DD' bucket, same as the aggregate's own
    date) + agent when given. Used by routers/metrics.py to populate each
    aggregate response's eventIds field."""
    events = read_raw_events(event_type=event_type, agent_name=agent_name)
    return [event for event in events if str(event.get("payload", {}).get("date", "")).startswith(date_bucket)]
