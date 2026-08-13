"""
Pydantic model for the Memoria de Mar (system-level, not per-project) —
SPEC_JARVIS.md §6.3.

Shape matches storage/mar-memory.json exactly:

    {
      entries: [
        {
          id: "mem_xxx",
          type: "understanding" | "open_question" | "correction",
          content: "...",
          createdAt: "2026-08-12T...",
          source: "chat" | "manual"
        }
      ]
    }
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_entry_id() -> str:
    return f"mem_{int(time.time() * 1000)}"


class MarMemoryEntry(BaseModel):
    id: str = Field(default_factory=_new_entry_id)
    type: Literal["understanding", "open_question", "correction"]
    content: str
    createdAt: str = Field(default_factory=_now_iso)
    source: Literal["chat", "manual"] = "manual"


class MarMemoryWriteRequest(BaseModel):
    """Body for POST /mar/memory. `id` is optional — omit it to let the
    service decide whether this is a new entry or an update of an existing
    near-duplicate (same type + similar content); pass it to force an
    update of a specific entry."""

    id: str | None = None
    type: Literal["understanding", "open_question", "correction"]
    content: str
    source: Literal["chat", "manual"] = "manual"
