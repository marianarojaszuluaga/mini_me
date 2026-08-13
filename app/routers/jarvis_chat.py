"""
POST /jarvis/chat — the Jarvis Chat agentic loop
(ARCHITECTURE_JARVIS.md §2.1, SPEC_JARVIS.md HU-006-JarvisMode).

Sequence per turn:
  1. session_manager opens/resumes the ChatSession (purpose required if new).
  2. Build context: full Memoria de Mar + active projects summary, plus this
     session's prior turns as conversation history.
  3. Call Claude with the 5 tools enabled (tools.TOOL_SCHEMAS).
  4. Loop while Claude asks for tool calls: dispatch each via
     tools.dispatch_tool, feed results back, let Claude decide if it needs
     another round.
  5. Persist the finished turn (message, tools used, sources cited).
  6. If the session is now near its context-token threshold, version it and
     return the new conversation_id so the frontend switches to it.
"""

from __future__ import annotations

import uuid
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.security import authenticate_token
from app.core.storage import get_storage
from app.schemas.chat import ChatRequest, ChatTurn, ChatTurnResponse, SourceCitation, ToolCallRecord
from app.services import mar_memory
from app.services.jarvis_chat import session_manager
from app.services.jarvis_chat.tools import TOOL_SCHEMAS, dispatch_tool

router = APIRouter(dependencies=[Depends(authenticate_token)])

CHAT_MODEL = "claude-3-5-sonnet-20241022"
CHAT_MAX_TOKENS = 4096

# Which tool name maps to which SourceCitation.kind (ARCHITECTURE_JARVIS.md §2.2).
_TOOL_TO_SOURCE_KIND: dict[str, str] = {
    "read_project_brain": "project_brain",
    "read_timeline": "timeline",
    "read_reconciliation": "reconciliation",
    "invoke_agent": "agent_invocation",
    "write_mar_memory": "mar_memory",
}

# Phrases that, when they appear in Claude's final answer, count as an
# explicit "no lo sé" (SPEC_JARVIS.md §3 Flujo C.5: never invent progress).
# TODO: calibrar en implementacion — a keyword check is a coarse proxy; a
# structured "I don't know" tool-less signal (e.g. asking Claude to prefix
# such answers) would be more reliable once this is exercised with real use.
_UNKNOWN_MARKERS = ("no lo sé", "no lo se", "no tengo información", "no tengo suficiente")


def _get_client(settings: Settings = Depends(get_settings)) -> AsyncAnthropic:
    return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


def _build_system_prompt(project_id: str | None, resumption_summary: str | None) -> str:
    mar_entries = mar_memory.get_all_entries()
    projects = get_storage().read_projects()
    active_projects = [
        {"id": p.get("id"), "name": p.get("name"), "status": p.get("status"), "currentStep": p.get("currentStep")}
        for p in projects
        if p.get("status") == "active"
    ]

    parts = [
        "Eres Jarvis, el asistente conversacional de Orquestrador 360. Respondes preguntas "
        "sobre proyectos citando explícitamente tus fuentes (usando las herramientas "
        "disponibles), o dices explícitamente que no lo sabes. Nunca inventas avance ni "
        "estado de un proyecto sin evidencia.",
        f"Memoria de Mar (entendimiento acumulado del sistema): {mar_entries!r}",
        f"Proyectos activos: {active_projects!r}",
    ]
    if project_id:
        parts.append(f"El foco de esta sesión es el proyecto: {project_id}")
    if resumption_summary:
        parts.append(f"Resumen de la sesión anterior (continúa desde aquí):\n{resumption_summary}")
    return "\n\n".join(parts)


def _turns_to_messages(turns: list[ChatTurn]) -> list[MessageParam]:
    """Flattens prior turns into plain user/assistant messages for context.
    Tool-call detail isn't replayed verbatim (Claude doesn't need its own
    past tool_use blocks to answer a new question) — the assistant_message
    text already carries whatever mattered from those tool results."""
    messages: list[MessageParam] = []
    for turn in turns:
        messages.append({"role": "user", "content": turn.role_user_message})
        messages.append({"role": "assistant", "content": turn.assistant_message})
    return messages


async def _run_agentic_loop(
    client: AsyncAnthropic,
    system_prompt: str,
    messages: list[MessageParam],
) -> tuple[str, list[ToolCallRecord], int, int]:
    """Runs the call -> tool_use -> tool_result -> call loop until Claude
    returns a text-only response. Returns (final_text, tool_calls,
    total_input_tokens, total_output_tokens)."""
    tool_calls: list[ToolCallRecord] = []
    total_input_tokens = 0
    total_output_tokens = 0

    # Safety bound so a misbehaving tool loop can't run forever.
    # TODO: calibrar en implementacion.
    max_iterations = 10

    for _ in range(max_iterations):
        response = await client.messages.create(
            model=CHAT_MODEL,
            max_tokens=CHAT_MAX_TOKENS,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            final_text = "".join(block.text for block in response.content if block.type == "text")
            return final_text, tool_calls, total_input_tokens, total_output_tokens

        # Claude wants to call one or more tools before continuing.
        messages.append({"role": "assistant", "content": response.content})

        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = await dispatch_tool(block.name, block.input)
            tool_calls.append(
                ToolCallRecord(
                    tool_name=block.name,
                    tool_input=block.input,
                    tool_result_summary=str(result)[:500],
                    tool_result=result,
                )
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    # Hit max_iterations without a final text response — surface what we
    # have rather than silently truncating the loop.
    return (
        "No pude completar esta respuesta dentro del límite de pasos de herramientas. "
        "Intenta reformular la pregunta o dividirla en partes más pequeñas.",
        tool_calls,
        total_input_tokens,
        total_output_tokens,
    )


def _build_sources(tool_calls: list[ToolCallRecord]) -> list[SourceCitation]:
    sources: list[SourceCitation] = []
    for call in tool_calls:
        kind = _TOOL_TO_SOURCE_KIND.get(call.tool_name, "none")
        ref = call.tool_input.get("project_id") or call.tool_input.get("agent_name") or None
        sources.append(SourceCitation(kind=kind, ref=ref, excerpt=call.tool_result_summary))
    return sources


def _declared_unknown(final_text: str) -> bool:
    lowered = final_text.lower()
    return any(marker in lowered for marker in _UNKNOWN_MARKERS)


@router.post("/jarvis/chat", response_model=ChatTurnResponse)
async def jarvis_chat(
    body: ChatRequest,
    client: AsyncAnthropic = Depends(_get_client),
) -> ChatTurnResponse:
    try:
        session = session_manager.open_or_resume(body.conversation_id, body.purpose, body.project_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    system_prompt = _build_system_prompt(session.project_id, session.resumption_summary)
    messages = _turns_to_messages(session.turns)
    messages.append({"role": "user", "content": body.message})

    final_text, tool_calls, input_tokens, output_tokens = await _run_agentic_loop(
        client, system_prompt, messages
    )

    turn = ChatTurn(
        id=str(uuid.uuid4()),
        role_user_message=body.message,
        assistant_message=final_text,
        tools_used=tool_calls,
        sources_cited=_build_sources(tool_calls),
        declared_unknown=_declared_unknown(final_text),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    session_with_turn = session_manager.persist_turn(session, turn)

    new_conversation_id: str | None = None
    if session_manager.is_near_context_limit(session_with_turn):
        next_session = session_manager.version_session(session_with_turn)
        new_conversation_id = next_session.id

    return ChatTurnResponse(
        conversation_id=session_with_turn.id,
        version=session_with_turn.version,
        turn=turn,
        session_status="closed" if new_conversation_id else "open",
        new_conversation_id=new_conversation_id,
    )
