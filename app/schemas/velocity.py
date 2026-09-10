"""
Velocity/Speed/Rollover/Completion metrics (Tarea 2, reunión CTO Angela
Forero, QA/KPI, 2026-09-10). Builds the "burndown de 3 líneas" she asked
for: planeado (WeeklyCommitment.committed_items) vs. reportado (completed
items the PM records) vs. lo que el código/evidencia realmente refleja
(derived from app/services/brain/reconciliation.py's gaps, already
persisted per project — the "3rd line" already exists, this just surfaces
it alongside the other two instead of duplicating it).

completed_items is a MANUAL field (see WeeklyCommitment docstring below) —
not derivable from existing data. We looked at reconciliation runs
(ReconciliationRun.gaps_closed_since_last) as a candidate proxy, but a
"gap closed" and a "committed item completed" are not the same unit: a
week's commitment is PM-defined work items (features/tickets), while
reconciliation gaps are AC-level test/code discrepancies — conflating them
would silently misrepresent velocity. So completed_items stays an explicit
PM input, clearly documented as such, while the reconciliation-derived
series is kept separate and labeled as what it actually is.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WeeklyCommitment(BaseModel):
    """One week's commitment for a project, registered by the PM (or
    whoever owns planning) at (or near) the start of the week.

    completed_items REQUIRES MANUAL INPUT from the PM — there is no existing
    event in metrics/collector.py or reconciliation.py that maps 1:1 to
    "work items the team committed to and finished this week" (reconciliation
    tracks AC/test gaps, not planning-level items). If this ever changes
    (e.g. a future integration with a board that has real item-level
    status), completed_items should be derived instead of asked for — until
    then, GET /projects/{id}/velocity computes completion_rate/rollover from
    whatever value was registered here, never fabricating one.
    """

    project_id: str
    week_start: date_type = Field(description="Monday of the week this commitment covers, ISO date")
    committed_items: int = Field(ge=0)
    completed_items: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Manual PM input — items actually completed this week. None until "
            "the PM registers it; treated as 0 completed (not 'unknown') only "
            "for rollover math once the week has fully elapsed."
        ),
    )
    owner_user_id: str | None = None
    createdAt: datetime = Field(default_factory=_utcnow)


class WeeklyVelocityPoint(BaseModel):
    """One week's row in the velocity series returned by GET /velocity —
    combines the PM-reported commitment with the reconciliation-derived
    3rd line for the same project/week bucket."""

    week_start: date_type
    committed_items: int
    completed_items: int | None
    velocity: int | None = Field(description="= completed_items for this week (None if not yet reported)")
    rollover: int = Field(
        default=0,
        description="committed_items not completed this week, carried into the next week's implicit backlog",
    )
    completion_rate: float | None = Field(
        default=None,
        description="completed_items / committed_items for this week, 0..1 (None if committed_items is 0 or completion not yet reported)",
    )
    # The "3rd line": derived from reconciliation, never manually entered.
    reconciliation_gaps_found: int | None = None
    reconciliation_gaps_closed: int | None = None


class VelocitySeries(BaseModel):
    project_id: str
    points: list[WeeklyVelocityPoint] = Field(default_factory=list)
