"""
TOOL REGISTRY — migrated from src/orchestrator.js's toolRegistry + callTool.

Today there is only one tool ("map"), and unlike the Node era it no longer
points at a separate Node service — MAP now lives in this same FastAPI app
(app/routers/agents.py, app/routers/projects.py, etc.), so MAP_URL should
simply point back at this backend's own base URL (e.g. http://localhost:8000
locally, or the deployed backend's public URL). MAP_URL is read from
app/core/config.py; if it isn't set, fall back to the same
http://localhost:{PORT} convention the JS original used.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.orchestrator import ToolInfo


class ToolError(Exception):
    """Raised when a tool lookup or invocation fails. `status` mirrors the
    HTTP status the JS original attached to its Error objects."""

    def __init__(self, message: str, status: int = 500) -> None:
        super().__init__(message)
        self.status = status


def _map_url() -> str:
    settings = get_settings()
    return settings.MAP_URL or f"http://localhost:{settings.PORT}"


def _build_tool_registry() -> dict[str, ToolInfo]:
    return {
        "map": ToolInfo(
            name="MAP",
            description="Multi-Agent Project Manager — 19 agents across 5 SDLC phases",
            url=_map_url(),
            available=["projects", "agents", "phases", "orchestrate", "evaluate"],
            inputs=["projectId", "phase", "step"],
            outputs=["project", "agentResult", "evaluation"],
        )
    }


def get_tool_registry() -> dict[str, ToolInfo]:
    """Rebuilt on each call (cheap, no I/O) so a MAP_URL change via settings
    reload is picked up without restarting the process — the JS original
    computed MAP_URL once at module load, but there's no reason to keep that
    limitation here."""
    return _build_tool_registry()


def list_tools() -> list[ToolInfo]:
    return list(get_tool_registry().values())


def get_tool(name: str) -> ToolInfo | None:
    return get_tool_registry().get(name)


async def call_tool(
    tool_name: str, action: str, body: dict[str, Any], token: str
) -> dict[str, Any]:
    """Async port of callTool(toolName, action, body, token): POSTs to
    `{tool.url}/{action}` with the caller's bearer token, same as the JS
    original's fetch call."""
    tool = get_tool(tool_name)
    if tool is None:
        raise ToolError(f"Tool not found: {tool_name}", status=404)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{tool.url}/{action}",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    if response.status_code >= 400:
        raise ToolError(f"Tool {tool_name} failed: {response.reason_phrase}", status=500)

    return response.json()
