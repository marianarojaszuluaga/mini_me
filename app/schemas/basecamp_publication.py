"""
Basecamp Message Board Publisher — modelo de dominio (2026-09-07).

Adaptado de SPEC-basecamp-message-board-publisher.md §1.7. El spec original
asume una tabla SQL con `UNIQUE (sprint_id, event_type)` para idempotencia —
orquestrador-360 usa Redis/JSON (app/core/storage.py), sin constraints
relacionales, así que la idempotencia se aplica en código: antes de insertar,
`basecamp_publisher.py` busca una fila existente con el mismo
(sprint_id, event_type) en la serie `basecamp-publications` y no duplica.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal["sprint.started", "sprint.closed"]
PublicationStatus = Literal["pending", "sent", "failed"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BasecampPublication(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    sprint_id: str
    project_id: str  # id interno de Project, no el bucket_id de Basecamp
    event_type: EventType
    bucket_id: str  # project_id de Basecamp
    message_board_id: str
    basecamp_message_id: str | None = None
    basecamp_url: str | None = None
    status: PublicationStatus = "pending"
    attempts: int = 0
    last_error: str | None = None
    created_at: str = Field(default_factory=_now_iso)
    sent_at: str | None = None
    # Guarda el payload con el que se renderizó el post: no hay dominio de
    # Sprint real (§4 del plan de reintentos) del que releer "los datos
    # actuales", así que un reintento vuelve a renderizar con este mismo
    # payload en vez de datos frescos inexistentes.
    payload: dict[str, Any] = Field(default_factory=dict)


class SprintStartedPayload(BaseModel):
    sprint_name: str
    goal: str | None = None
    period: dict[str, str]  # {"start": "...", "end": "..."}
    committed: int
    owners: list[str] = Field(default_factory=list)
    scope: list[dict[str, Any]] = Field(default_factory=list)  # [{title, url, owner}]


class SprintClosedPayload(BaseModel):
    sprint_name: str
    goal: str | None = None
    period: dict[str, str]
    committed: int
    completed: int
    carry_over: list[dict[str, Any]] = Field(default_factory=list)  # [{title, url}]
