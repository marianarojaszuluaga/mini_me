"""
TOOLCHAIN EXECUTION — migrated from src/orchestrator.js's executeToolchain.

Shared by POST /toolchain/execute AND POST /workflows/{id}/execute — no
internal HTTP call to itself (the JS comment explains this relied on
`localhost`, which serverless invocations don't share; here it's simply a
shared async function called directly from both router handlers).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.storage import get_storage
from app.schemas.orchestrator import ToolchainStep
from app.services.orchestrator.tool_registry import ToolError, call_tool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def execute_toolchain(
    sequence: list[ToolchainStep], data: dict[str, Any] | None, token: str
) -> dict[str, Any]:
    if not sequence:
        raise ToolError("sequence must be array of {tool, action}", status=400)

    current_data: dict[str, Any] = data or {}
    results: list[dict[str, Any]] = []
    storage = get_storage()

    for step in sequence:
        result = await call_tool(step.tool, step.action, current_data, token)
        results.append({"tool": step.tool, "action": step.action, "result": result})

        current_data = result if step.passOutput else current_data
        storage.log_tool_invocation(
            {
                "timestamp": _now(),
                "tool": step.tool,
                "action": step.action,
                "status": "success",
            }
        )

    return {
        "sequence": [step.model_dump() for step in sequence],
        "results": results,
        "finalData": current_data,
        "timestamp": _now(),
    }
