"""
Pydantic schemas for the Analytics/Metrics layer.

Covers HU-008-JarvisMode (multidimensional continuous self-evaluation),
HU-009-JarvisMode (system improvement changelog — consumes AgentEvaluation
series to detect the "2 consecutive low-quality invocations" threshold
decided in SPEC_JARVIS.md §10), and HU-010-JarvisMode (business analytics
panel — consumes all four schemas below as its time series), per the P0-P3
priority table in SPEC_JARVIS.md §7.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

OutputType = Literal[
    "hu",
    "spec",
    "plan",
    "acta",
    "evaluacion",
    "reconciliacion",
    # Added 2026-08-14 (Mariana: "robustecer las analíticas... outputs de
    # todos los agentes") — qa_run covers vale/sara/xime's QA-phase agents,
    # pull_request is recorded from the repo digest (sync_scheduler.py),
    # not from an agent invocation directly.
    "qa_run",
    "pull_request",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentEvaluation(BaseModel):
    """One evaluated invocation of an agent — the four dimensions of
    HU-008-JarvisMode. Deliberately NOT a single avgScore: eficiencia,
    acertividad, formato and calidad are tracked as independent series so
    HU-010's analytics panel can chart them separately, and HU-009's
    changelog can point at exactly which dimension degraded.
    """

    agent: str
    date: datetime = Field(default_factory=_utcnow)
    eficiencia: float = Field(ge=0, le=100)
    acertividad: float = Field(ge=0, le=100)
    formato: float = Field(ge=0, le=100)
    calidad: float = Field(ge=0, le=100)
    count: int = Field(
        default=1,
        description="Number of invocations this record aggregates (1 for a raw per-invocation record).",
    )


class ReconciliationRun(BaseModel):
    """One reconciliation pass over a project's Acceptance Criteria vs. real
    tests (ARCHITECTURE_JARVIS.md §5). gaps_found/gaps_closed_since_last are
    the P0 metric from SPEC_JARVIS.md §7: "la métrica más contundente contra
    el escepticismo".
    """

    project_id: str
    date: datetime = Field(default_factory=_utcnow)
    gaps_found: int = Field(ge=0)
    gaps_closed_since_last: int = Field(ge=0)
    sin_test: int = Field(
        ge=0,
        description="ACs with no associated test found — reported as 'sin test', never as 'cumple' (§5).",
    )


class UsageEvent(BaseModel):
    """Daily rollup of usage — P0 metric 'número de usos' from SPEC_JARVIS.md
    §7. chat_messages and agent_invocations are tracked separately since one
    chat turn can trigger zero, one, or several agent invocations."""

    date: datetime = Field(default_factory=_utcnow)
    chat_messages: int = Field(default=0, ge=0)
    agent_invocations: int = Field(default=0, ge=0)


class OutputCount(BaseModel):
    """Independent per-type output counter — the P0 'base de todo lo demás'
    metric (SPEC_JARVIS.md §7): HUs, specs, planes, actas, evaluaciones y
    reconciliaciones are counted separately, never mixed into one total.

    project_id/agent_name added 2026-08-14: the Dashboard's "Estadísticas
    del proyecto" section must show real outputs scoped to ONE project, not
    a system-wide total (Mariana: "la info es por proyecto no general") —
    both are optional because some output types (e.g. a manual agent
    invocation with no project context) genuinely have neither."""

    type: OutputType
    count: int = Field(ge=0)
    date: datetime = Field(default_factory=_utcnow)
    project_id: str | None = None
    agent_name: str | None = None


RawEventType = Literal[
    "agent_evaluation",
    "reconciliation_run",
    "usage_event",
    "output_count",
]


class RawMetricEvent(BaseModel):
    """One individual, drill-down-able raw event (SPEC_JARVIS.md HU-010,
    AC6: "Cada número tiene un control de drill-down que lleva a los eventos
    crudos que lo componen"). Written alongside (never instead of) the
    aggregate series in collector.py, so time-series dashboards keep reading
    the fast aggregates while drill-down queries this series instead.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: RawEventType
    agent_name: str | None = None
    timestamp: datetime = Field(default_factory=_utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)
