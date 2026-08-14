"""
The 5 tools Claude can call during a Jarvis Chat turn
(ARCHITECTURE_JARVIS.md §2.2). Each tool is declared as an Anthropic
`input_schema` tool spec (TOOL_SCHEMAS, passed verbatim as `tools=` to
messages.create) plus an async Python resolver, wired together in
TOOL_RESOLVERS so the router's agentic loop can dispatch by name without a
big if/elif chain.

Resolvers always return a JSON-serializable dict. On a lookup miss (unknown
project_id, etc.) they return `{"found": False, ...}` rather than raising —
a raised exception inside the loop would abort the whole chat turn instead
of letting Claude see "not found" and say so explicitly (SPEC_JARVIS.md §3
Flujo C.5: "no inventa avance", explicit "no lo sé" is a valid outcome, not
a bug).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.core.storage import get_storage
from app.schemas.mar_memory import MarMemoryEntry
from app.services import agent_registry, mar_memory
from app.services.brain import ingest as brain_ingest
from app.services.brain import reconciliation as brain_reconciliation

# ---------------------------------------------------------------------------
# Tool schemas — Anthropic SDK `input_schema` format
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "read_project_brain",
        "description": (
            "Reads a project's Project Brain: decision log, alerts, meeting "
            "log, and the last reconciliation summary. Use this to answer "
            "any question about a project's decisions, risks, or status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The id of the project to read.",
                },
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "read_timeline",
        "description": (
            "Reads recent raw activity events for a project (commits, agent "
            "invocations, phase transitions) over the last N days. Use this "
            "for 'what happened recently' style questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The id of the project to read.",
                },
                "days": {
                    "type": "integer",
                    "description": "How many days back to look. Defaults to 7.",
                },
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "read_reconciliation",
        "description": (
            "Reads the open/closed Acceptance Criteria gaps for a project — "
            "i.e. what's claimed done vs. what actually has evidence/tests. "
            "Use this before ever telling the user something is 'done'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The id of the project to check.",
                },
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "invoke_agent",
        "description": (
            "Invokes one of the 22 real MAP agents (e.g. 'gime', 'gabi', "
            "'vale') with a given input, and returns its output. Use this "
            "when the user explicitly asks Jarvis to run an agent, not for "
            "answering questions Jarvis can answer from context alone."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Registered agent id, e.g. 'gime', 'gabi', 'vale'.",
                },
                "input": {
                    "type": "string",
                    "description": "The input/prompt to give the agent.",
                },
                "project_id": {
                    "type": "string",
                    "description": "Project this invocation belongs to, if any.",
                },
            },
            "required": ["agent_name", "input"],
        },
    },
    {
        "name": "write_mar_memory",
        "description": (
            "Saves or updates an entry in Memoria de Mar (the living "
            "glossary of what Mar has taught Jarvis about the system). Use "
            "this when the user corrects an assumption or states something "
            "worth remembering across sessions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Category of the entry, e.g. 'preference', 'correction', 'fact'.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to remember, in plain language.",
                },
                "source": {
                    "type": "string",
                    "description": "Where this came from, e.g. 'jarvis_chat'.",
                },
            },
            "required": ["type", "content"],
        },
    },
]


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


async def read_project_brain(project_id: str) -> dict[str, Any]:
    projects = get_storage().read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if project is None:
        return {"found": False, "project_id": project_id, "reason": "project not found"}

    brain = project.get("memory", {}).get("projectBrain", {})
    return {
        "found": True,
        "project_id": project_id,
        "status": brain.get("status"),
        "decisionLog": brain.get("decisionLog", []),
        "alerts": brain.get("alerts", []),
        "meetingLog": brain.get("meetingLog", []),
        "reconciliation": brain.get("reconciliation"),
    }


async def read_timeline(project_id: str, days: int = 7) -> dict[str, Any]:
    """Recent raw activity events for a project — delegates to
    app.services.brain.ingest.list_recent_events."""
    events = brain_ingest.list_recent_events(project_id, days)
    if events is None:
        return {"found": False, "project_id": project_id, "reason": "project not found"}
    return {"found": True, "project_id": project_id, "days": days, "events": events}


async def read_reconciliation(project_id: str) -> dict[str, Any]:
    """Open/closed AC gaps for a project — delegates to
    app.services.brain.reconciliation.get_latest."""
    projects = get_storage().read_projects()
    if not any(p.get("id") == project_id for p in projects):
        return {"found": False, "project_id": project_id, "reason": "project not found"}

    reconciliation = brain_reconciliation.get_latest(project_id)
    if not reconciliation:
        return {
            "found": True,
            "project_id": project_id,
            "gaps": [],
            "lastRunAt": None,
            "note": "No reconciliation has run yet for this project.",
        }
    return {
        "found": True,
        "project_id": project_id,
        "gaps": reconciliation.get("gaps", []),
        "lastRunAt": reconciliation.get("lastRunAt"),
    }


async def invoke_agent(agent_name: str, input: str, project_id: str | None = None) -> dict[str, Any]:  # noqa: A002 - matches tool schema param name
    """Invokes a real agent and returns its output.

    Deliberately self-contained (not delegating to routers/agents.py's
    invoke_agent_core) — per ARCHITECTURE_JARVIS.md §0's layering rule, a
    service must not import a router; the handful of lines duplicated here
    (build prompt -> call model -> log activity) are the same steps
    invoke_agent_core performs, just callable from the chat tool loop
    without an internal HTTP round-trip.
    """
    if not agent_registry.is_known_agent(agent_name):
        return {"found": False, "agent_name": agent_name, "reason": "unknown agent"}

    prompt = agent_registry.build_prompt(agent_name, input, {"project_id": project_id} if project_id else None)
    if prompt is None:
        return {"found": False, "agent_name": agent_name, "reason": "agent prompt could not be built"}

    model_config = agent_registry.get_model_config(agent_name)
    settings = get_settings()
    client = AsyncAnthropic(**settings.anthropic_client_kwargs)

    kwargs: dict[str, Any] = {
        "model": model_config["model"],
        "max_tokens": model_config["max_tokens"],
        "messages": [{"role": "user", "content": prompt.user}],
    }
    if prompt.system:
        kwargs["system"] = prompt.system

    response = await client.messages.create(**kwargs)
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    storage = get_storage()
    storage.log_activity(
        {
            "timestamp": timestamp,
            "projectId": project_id,
            "agent": agent_name,
            "action": "invoked_via_jarvis_chat",
            "status": "completed",
        }
    )

    return {
        "found": True,
        "agent_name": agent_name,
        "output": response.content[0].text,
        "model": model_config["model"],
        "timestamp": timestamp,
    }


async def write_mar_memory(type: str, content: str, source: str | None = "jarvis_chat", id: str | None = None) -> dict[str, Any]:  # noqa: A002
    entry = MarMemoryEntry(**({"id": id} if id else {}), type=type, content=content, source=source)
    saved = mar_memory.add_or_update_entry(entry)
    return {"saved": True, "entry": saved}


TOOL_RESOLVERS: dict[str, Any] = {
    "read_project_brain": read_project_brain,
    "read_timeline": read_timeline,
    "read_reconciliation": read_reconciliation,
    "invoke_agent": invoke_agent,
    "write_mar_memory": write_mar_memory,
}


async def dispatch_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Looks up and awaits the resolver for `tool_name` with `tool_input` as
    kwargs. Returns an error dict (never raises) on an unknown tool name, so
    the agentic loop can feed the error back to Claude as a tool_result
    instead of crashing the request."""
    resolver = TOOL_RESOLVERS.get(tool_name)
    if resolver is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return await resolver(**tool_input)
    except (TypeError, ValueError) as error:
        # TypeError: wrong/missing kwargs. ValueError: Pydantic validation
        # inside a resolver (e.g. write_mar_memory's `type` literal). Either
        # way, feed it back to Claude as a tool_result instead of a 500.
        return {"error": f"Invalid input for tool {tool_name}: {error}"}
