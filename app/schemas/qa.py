"""
QA sweep report schema — Tarea 3, integración del esquema real de Finanz
Butik (2026-08-24, planning-fb/qa/). Adopta su modelo de severidad + gate
mecánico: un veredicto nunca es "a ojo" de un agente, siempre se calcula en
Python a partir de los findings reales.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["S1", "S2", "S3", "S4", "S5"]

# S1/S2 = blocking (flow can't proceed / data loss / broken AC).
# S3-S5 = non-blocking, logged as change orders — same gate Finanz uses.
_BLOCKING_SEVERITIES = {"S1", "S2"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: f"BUG-{uuid.uuid4().hex[:8]}")
    criterionId: str | None = None
    title: str
    severity: Severity
    category: str | None = None
    description: str | None = None


class Signoff(BaseModel):
    reviewer: Literal["PM", "TechLead"]
    verdict: Literal["APPROVED", "NOT_APPROVED"]
    date: str = Field(default_factory=_now_iso)


class QaSweepReport(BaseModel):
    id: str = Field(default_factory=lambda: f"qa-sweep-{uuid.uuid4().hex[:10]}")
    projectId: str
    scope: Literal["project", "release"] = "project"
    createdAt: str = Field(default_factory=_now_iso)
    steps: dict[str, Any] = Field(default_factory=dict)
    reconciliation: dict[str, Any] | None = None
    findings: list[Finding] = Field(default_factory=list)
    report: str | None = None
    signoffs: list[Signoff] = Field(default_factory=list)

    @property
    def blockingCount(self) -> int:
        return sum(1 for f in self.findings if f.severity in _BLOCKING_SEVERITIES)

    @property
    def verdict(self) -> Literal["APPROVED", "NOT_APPROVED"]:
        return "NOT_APPROVED" if self.blockingCount > 0 else "APPROVED"

    def to_public_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["blockingCount"] = self.blockingCount
        data["verdict"] = self.verdict
        return data
