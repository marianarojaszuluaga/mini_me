"""
Pydantic models for Jarvis Chat — POST /jarvis/chat.

Shape matches ARCHITECTURE_JARVIS.md §2.3 exactly (ChatSession with mandatory
`purpose`, versioned instead of ever being deleted) and SPEC_JARVIS.md §6.6
(same fields, camelCase in the JSON store — storage/jarvis-sessions.json).

`ChatTurn` intentionally carries `tools_used` + `sources_cited` as first-class
fields (not folded into a free-form dict) because HU-006-JarvisMode's
Acceptance Criteria require every response to cite its source, or say
explicitly it doesn't know — that has to be a queryable field, not prose.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Request / response for POST /jarvis/chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Body of POST /jarvis/chat. `conversation_id` absent/None => a new
    session is opened (and `purpose` becomes mandatory — enforced in
    session_manager.open_or_resume, not here, since a resumed session
    doesn't need `purpose` repeated)."""

    conversation_id: str | None = None
    message: str
    # Required only when conversation_id is None. Optional on the schema
    # itself (Pydantic can't do "required if sibling is None" declaratively
    # without a model_validator) — session_manager raises a clear error if
    # a new session is requested without one.
    purpose: str | None = None
    project_id: str | None = None


class ToolCallRecord(BaseModel):
    """One tool invocation that happened while producing a single ChatTurn."""

    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_result_summary: str | None = None
    # Raw JSON-able result, kept so the frontend timeline can drill down
    # without re-fetching (Panel de Estado, ARCHITECTURE_JARVIS.md §2.1).
    tool_result: Any = None


class SourceCitation(BaseModel):
    """A concrete thing Jarvis's answer points to — never a vague appeal to
    memory. `kind` names which of the 5 tools (or "none") produced it."""

    kind: Literal[
        "project_brain",
        "timeline",
        "reconciliation",
        "agent_invocation",
        "mar_memory",
        "none",
    ]
    ref: str | None = None
    excerpt: str | None = None


class ChatTurn(BaseModel):
    """One user message + Jarvis's final answer, plus everything that
    happened in between (ARCHITECTURE_JARVIS.md §2.1's agentic loop)."""

    id: str
    role_user_message: str
    assistant_message: str
    tools_used: list[ToolCallRecord] = Field(default_factory=list)
    sources_cited: list[SourceCitation] = Field(default_factory=list)
    # True when Claude explicitly said it doesn't have enough information —
    # SPEC_JARVIS.md §3 Flujo C.5: "no inventa avance".
    declared_unknown: bool = False
    timestamp: str = Field(default_factory=_now_iso)
    # Token usage of this turn's model call(s), used by session_manager to
    # decide when to version the session (§2.3).
    input_tokens: int = 0
    output_tokens: int = 0


class ChatSession(BaseModel):
    """Exact shape of ARCHITECTURE_JARVIS.md §2.3 / SPEC_JARVIS.md §6.6.
    Persisted as one entry in storage/jarvis-sessions.json via
    core/storage.py's read_chat_sessions/write_chat_sessions."""

    id: str
    purpose: str  # mandatory — "no hay sesión sin propósito"
    project_id: str | None = None
    status: Literal["open", "closed"] = "open"
    version: int = 1  # v2/v3 if the same purpose is resumed later
    turns: list[ChatTurn] = Field(default_factory=list)
    opened_at: str = Field(default_factory=_now_iso)
    closed_at: str | None = None
    # Set when this session was spawned because a previous version hit the
    # context-size threshold — points at the version it continues from.
    resumed_from_session_id: str | None = None
    # First-turn summary injected when resuming from a prior version, so the
    # user doesn't notice the cut (ARCHITECTURE_JARVIS.md §2.3).
    resumption_summary: str | None = None


class ChatTurnResponse(BaseModel):
    """What POST /jarvis/chat returns — the new turn plus enough session
    metadata for the frontend to keep talking, and to refresh the Panel de
    Estado in the same request/response (no separate socket in v1)."""

    conversation_id: str
    version: int
    turn: ChatTurn
    session_status: Literal["open", "closed"]
    # Present only when this turn triggered a version cut.
    new_conversation_id: str | None = None
