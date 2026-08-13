"""
Metrics collector — writes the time-series records defined in
app/schemas/metrics.py to storage. This is the single write path for the
Analytics layer (ARCHITECTURE_JARVIS.md §4, §7 / SPEC_JARVIS.md §7); readers
live in app/routers/metrics.py.

Series names (storage.py series/file names, one JSON list each):
- "metrics-agent-evaluations" -> list[AgentEvaluation]
- "metrics-reconciliation-runs" -> list[ReconciliationRun]
- "metrics-usage-events" -> list[UsageEvent]   (one entry per day, upserted)
- "metrics-output-counts" -> list[OutputCount] (one entry per type per day, upserted)
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.storage import get_storage
from app.schemas.metrics import (
    AgentEvaluation,
    OutputCount,
    OutputType,
    ReconciliationRun,
    UsageEvent,
)

_AGENT_EVAL_SERIES = "metrics-agent-evaluations"
_RECONCILIATION_SERIES = "metrics-reconciliation-runs"
_USAGE_SERIES = "metrics-usage-events"
_OUTPUT_SERIES = "metrics-output-counts"


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


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
    return evaluation


async def record_output(output_type: OutputType) -> OutputCount:
    """Increments today's counter for a given output type (HU/spec/plan/acta/
    evaluacion/reconciliacion) — P0 metric, independent counter per type."""
    storage = get_storage()
    today = _today_iso()
    counts = storage.read_series(_OUTPUT_SERIES)

    for row in counts:
        if row.get("type") == output_type and row.get("date", "").startswith(today):
            row["count"] = row.get("count", 0) + 1
            storage.write_series(_OUTPUT_SERIES, counts)
            return OutputCount(**row)

    record = OutputCount(type=output_type, count=1)
    counts.append(record.model_dump(mode="json"))
    storage.write_series(_OUTPUT_SERIES, counts)
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
            return UsageEvent(**row)

    record = UsageEvent(
        chat_messages=1 if chat_message else 0,
        agent_invocations=1 if agent_invocation else 0,
    )
    events.append(record.model_dump(mode="json"))
    storage.write_series(_USAGE_SERIES, events)
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


def read_output_counts() -> list[dict]:
    return get_storage().read_series(_OUTPUT_SERIES)
