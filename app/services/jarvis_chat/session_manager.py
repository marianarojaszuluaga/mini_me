"""
Jarvis Chat session lifecycle — open/resume, context-limit detection, and
versioning (ARCHITECTURE_JARVIS.md §2.3).

Persistence goes through app.core.storage.get_storage().read_chat_sessions() /
write_chat_sessions() (added there alongside read_mar_memory, same
{"sessions": [...]} wrapper convention) — sessions are stored as one flat
list, each entry the JSON dump of a ChatSession.

Versioning contract: a ChatSession is never mutated into "not existing" —
when it's about to blow the context window, it's marked status="closed" and
a *new* session is opened with the same `purpose`/`project_id`, `version + 1`,
and a `resumption_summary` carrying forward what mattered. The `id` changes
(new UUID) because callers key turns/API responses off (conversation_id,
version) as a pair; `resumed_from_session_id` links them so history stays
walkable backwards.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.storage import get_storage
from app.schemas.chat import ChatSession, ChatTurn

# TODO: calibrar en implementacion — accumulated input+output tokens across a
# session's turns before we proactively version it. Claude's context windows
# run 200k tokens; 120k leaves headroom for the next turn's tool-call
# round-trips (project brain + timeline + reconciliation reads all get
# concatenated into context) without truncation ever kicking in mid-turn.
CONTEXT_TOKEN_THRESHOLD = 120_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return str(uuid.uuid4())


def _load_all() -> list[dict[str, Any]]:
    return get_storage().read_chat_sessions()


def _save_all(sessions: list[dict[str, Any]]) -> None:
    get_storage().write_chat_sessions(sessions)


def get_session(session_id: str) -> ChatSession | None:
    for raw in _load_all():
        if raw.get("id") == session_id:
            return ChatSession.model_validate(raw)
    return None


def accumulated_tokens(session: ChatSession) -> int:
    """Sum of input+output tokens across every turn recorded so far in this
    session version — the proxy used to decide when to version (§2.3)."""
    return sum(turn.input_tokens + turn.output_tokens for turn in session.turns)


def is_near_context_limit(session: ChatSession) -> bool:
    return accumulated_tokens(session) >= CONTEXT_TOKEN_THRESHOLD


def open_new_session(purpose: str, project_id: str | None = None) -> ChatSession:
    """Opens a brand-new session (version 1). `purpose` is mandatory — there
    is no session without a purpose (ARCHITECTURE_JARVIS.md §2.3)."""
    if not purpose or not purpose.strip():
        raise ValueError("purpose is required to open a new Jarvis Chat session")

    session = ChatSession(
        id=_new_id(),
        purpose=purpose.strip(),
        project_id=project_id,
        status="open",
        version=1,
        turns=[],
    )
    sessions = _load_all()
    sessions.append(session.model_dump())
    _save_all(sessions)
    return session


def open_or_resume(
    conversation_id: str | None,
    purpose: str | None,
    project_id: str | None,
) -> ChatSession:
    """Entry point for POST /jarvis/chat. If `conversation_id` is None, opens
    a new session (requires `purpose`). If it's set, loads that session's
    history — raising if it doesn't exist, since a client sending a stale/
    unknown conversation_id is a bug, not a "create silently" situation."""
    if conversation_id is None:
        if not purpose:
            raise ValueError(
                "purpose is required when starting a new Jarvis Chat session "
                "(conversation_id is None)"
            )
        return open_new_session(purpose, project_id)

    session = get_session(conversation_id)
    if session is None:
        raise LookupError(f"Unknown conversation_id: {conversation_id}")
    if session.status == "closed":
        raise ValueError(
            f"conversation_id {conversation_id} is closed — start a new session "
            "(POST /jarvis/chat with conversation_id omitted and a purpose) instead "
            "of resuming a closed one"
        )
    return session


def close_session(conversation_id: str) -> ChatSession:
    """Explicit user-driven close (SPEC_JARVIS.md §11 — sessions must be
    opened/closed deliberately in the UI, not just cut by context-limit
    versioning). Idempotent: closing an already-closed session just returns
    it unchanged rather than erroring, since the frontend's "end session"
    action shouldn't fail on a double-click or a stale tab."""
    sessions = _load_all()
    session = get_session(conversation_id)
    if session is None:
        raise LookupError(f"Unknown conversation_id: {conversation_id}")
    if session.status == "closed":
        return session

    closed = session.model_copy(update={"status": "closed", "closed_at": _now_iso()})
    for i, raw in enumerate(sessions):
        if raw.get("id") == closed.id:
            sessions[i] = closed.model_dump()
            break
    _save_all(sessions)
    return closed


def _summarize_for_resumption(session: ChatSession) -> str:
    """Builds the first-message summary carried into the next version so the
    user doesn't notice the context cut (§2.3). Cheap, local heuristic — the
    last few turns' assistant messages plus the session purpose; a model-
    written summary is a reasonable v2 upgrade but not required to keep the
    thread coherent.

    TODO: calibrar en implementacion — consider summarizing via a Haiku call
    once real sessions are long enough to make truncation noticeable.
    """
    tail = session.turns[-6:]
    lines = [f'Sesion previa (v{session.version}) — proposito: "{session.purpose}".']
    for turn in tail:
        lines.append(f"- Usuaria: {turn.role_user_message}")
        lines.append(f"  Jarvis: {turn.assistant_message}")
    return "\n".join(lines)


def version_session(session: ChatSession) -> ChatSession:
    """Closes `session` (status="closed") and opens a new version with the
    same purpose/project_id, `version + 1`, and a resumption_summary. Returns
    the new session — callers should switch to using its id from here on."""
    sessions = _load_all()

    closed = session.model_copy(
        update={"status": "closed", "closed_at": _now_iso()}
    )
    summary = _summarize_for_resumption(closed)

    next_session = ChatSession(
        id=_new_id(),
        purpose=closed.purpose,
        project_id=closed.project_id,
        status="open",
        version=closed.version + 1,
        turns=[],
        resumed_from_session_id=closed.id,
        resumption_summary=summary,
    )

    replaced = False
    for i, raw in enumerate(sessions):
        if raw.get("id") == closed.id:
            sessions[i] = closed.model_dump()
            replaced = True
            break
    if not replaced:
        sessions.append(closed.model_dump())
    sessions.append(next_session.model_dump())

    _save_all(sessions)
    return next_session


def persist_turn(session: ChatSession, turn: ChatTurn) -> ChatSession:
    """Appends `turn` to `session` and writes it back. Returns the updated
    in-memory session (same id/version) — versioning, if warranted, is a
    separate explicit call by the router after checking
    is_near_context_limit(updated_session)."""
    sessions = _load_all()
    updated = session.model_copy(update={"turns": [*session.turns, turn]})

    replaced = False
    for i, raw in enumerate(sessions):
        if raw.get("id") == updated.id:
            sessions[i] = updated.model_dump()
            replaced = True
            break
    if not replaced:
        sessions.append(updated.model_dump())

    _save_all(sessions)
    return updated
