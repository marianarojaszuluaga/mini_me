"""
Pydantic schema for the system-improvement changelog (HU-009-JarvisMode,
SPEC_JARVIS.md §10). Consumes app/schemas/metrics.py's AgentEvaluation
series (the four dimensions from HU-008) to build a before/after comparison
for each prompt/config adjustment made to an agent.

Shape matches storage/changelog.json: a flat list of ChangelogEntry, same
convention as read_mar_memory's wrapped-list pattern (see
app/core/storage.py).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_entry_id() -> str:
    return f"chg_{int(time.time() * 1000)}"


class DimensionScores(BaseModel):
    """The four dimensions from HU-008-JarvisMode, averaged over a window.
    Never a single avg score — each dimension is reported independently so
    the changelog entry shows exactly which one moved."""

    eficiencia: float = Field(ge=0, le=100)
    acertividad: float = Field(ge=0, le=100)
    formato: float = Field(ge=0, le=100)
    calidad: float = Field(ge=0, le=100)
    sample_count: int = Field(
        ge=0, description="Number of AgentEvaluation records averaged into this window."
    )


class DateWindow(BaseModel):
    """Same-length before/after window (SPEC_JARVIS.md §10: 'usa la misma
    ventana de tiempo para ambos lados')."""

    start: datetime
    end: datetime


class ChangelogEntry(BaseModel):
    """One system-improvement changelog entry. Only ever created for an
    agent whose prompt/config was actually adjusted; `approved_at` is set
    exclusively by Mar's explicit action (services/changelog.approve_proposal)
    — never auto-set. `after_scores` stays None (not a fabricated number)
    until compute_after_scores() finds enough post-approval history."""

    id: str = Field(default_factory=_new_entry_id)
    agent_name: str
    what_changed: str = Field(description="Free-text description of the prompt/config adjustment.")
    reason: str = Field(
        description="Why the adjustment was proposed, e.g. "
        "'2 invocaciones seguidas bajas en formato'."
    )
    proposed_at: str = Field(default_factory=_now_iso)
    approved_at: str | None = Field(
        default=None, description="Set only by approve_proposal() — Mar's explicit approval."
    )
    applied_at: str | None = Field(
        default=None, description="When the adjustment was actually applied to the agent."
    )
    before_window: DateWindow
    after_window: DateWindow | None = Field(
        default=None,
        description="Set once approved — same length as before_window, starting at approved_at.",
    )
    before_scores: DimensionScores
    after_scores: DimensionScores | None = Field(
        default=None,
        description="None while there isn't enough post-approval history yet — the API/UI must "
        "render this as 'en progreso', never as an invented or projected number.",
    )
    status: Literal["proposed", "approved", "measured"] = "proposed"


class ChangelogCreateRequest(BaseModel):
    """Body for POST /changelog — creating a new proposal. Mirrors
    create_proposal()'s signature."""

    agent_name: str
    what_changed: str
    reason: str
    before_window: DateWindow
