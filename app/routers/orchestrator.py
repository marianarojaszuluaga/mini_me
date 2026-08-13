"""
MASTER ORCHESTRATOR — migrated from src/orchestrator.js.

Note on auth: unlike agents.py/projects.py (which require the auth
dependency), these routes are left unauthenticated here, matching how this
router is being wired up today (no `Depends(authenticate_token)` on the
APIRouter). The JS original did gate everything except /health behind
authenticateToken and forwarded req.token to callTool/executeToolchain — if
auth is added back later, thread the validated token through the same way
agents.py does.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from app.core.config import get_settings
from app.core.storage import get_storage
from app.schemas.orchestrator import (
    ToolchainRequest,
    Workflow,
    WorkflowCreate,
    WorkflowExecuteRequest,
)
from app.services.orchestrator import tool_registry, workflows_store
from app.services.orchestrator.toolchain import execute_toolchain
from app.services.orchestrator.tool_registry import ToolError

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _token_from_request(request: Request) -> str:
    """No auth dependency is mounted on this router (see module docstring),
    so there's no validated token from a security scheme — pass through
    whatever bearer token (if any) the caller sent, same value the JS
    original forwarded to callTool via req.token."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:]
    return ""


# ============================================================================
# HEALTH — stays unauthenticated, same rationale as app/routers/health.py
# ============================================================================


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "orchestrator",
        "timestamp": _now(),
        "tools": list(tool_registry.get_tool_registry().keys()),
    }


# ============================================================================
# REGISTRY
# ============================================================================


@router.get("/tools")
async def list_tools() -> list[dict[str, Any]]:
    return [tool.model_dump() for tool in tool_registry.list_tools()]


@router.get("/tools/{name}")
async def get_tool(name: str) -> dict[str, Any]:
    tool = tool_registry.get_tool(name)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool.model_dump()


# ============================================================================
# TOOL INVOCATION
# ============================================================================


@router.post("/tools/{tool_name}/{action}")
async def invoke_tool(
    tool_name: str,
    action: str,
    request: Request,
    body: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    token = _token_from_request(request)
    try:
        result = await tool_registry.call_tool(tool_name, action, body, token)
    except ToolError as error:
        raise HTTPException(status_code=error.status, detail=str(error)) from error

    get_storage().log_tool_invocation(
        {
            "timestamp": _now(),
            "tool": tool_name,
            "action": action,
            "status": "success",
        }
    )
    return {"tool": tool_name, "action": action, "timestamp": _now(), "result": result}


# ============================================================================
# TOOLCHAIN EXECUTION — chain multiple tools
# ============================================================================


@router.post("/toolchain/execute")
async def toolchain_execute(request: Request, body: ToolchainRequest) -> dict[str, Any]:
    token = _token_from_request(request)
    try:
        return await execute_toolchain(body.sequence, body.data, token)
    except ToolError as error:
        raise HTTPException(status_code=error.status, detail=str(error)) from error


# ============================================================================
# WORKFLOWS — save and execute tool sequences
# ============================================================================


@router.get("/workflows")
async def list_workflows() -> list[dict[str, Any]]:
    return workflows_store.list_workflows()


@router.post("/workflows", status_code=201)
async def create_workflow(payload: WorkflowCreate) -> dict[str, Any]:
    return workflows_store.create_workflow(payload)


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str, request: Request, body: WorkflowExecuteRequest
) -> dict[str, Any]:
    workflow = workflows_store.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    token = _token_from_request(request)
    sequence = Workflow.model_validate(workflow).sequence
    try:
        execution = await execute_toolchain(sequence, body.data, token)
    except ToolError as error:
        raise HTTPException(status_code=error.status, detail=str(error)) from error

    return {"workflow": workflow.get("name"), "execution": execution}


# ============================================================================
# SYSTEM STATE
# ============================================================================


@router.get("/system/state")
async def system_state() -> dict[str, Any]:
    settings = get_settings()
    storage = get_storage()
    return {
        "tools": list(tool_registry.get_tool_registry().keys()),
        "port": settings.ORCHESTRATOR_PORT,
        "storage": "vercel-kv" if storage.using_kv else "filesystem",
        "timestamp": _now(),
    }
