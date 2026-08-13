"""
Value objects for the Master Orchestrator (migrated from src/orchestrator.js).

ToolInfo mirrors the shape of an entry in toolRegistry. ToolchainStep/
ToolchainRequest mirror the {tool, action, passOutput} sequence steps and the
POST /toolchain/execute body. Workflow mirrors a saved sequence, persisted via
app/core/storage.py's read_workflows/write_workflows.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ToolInfo(BaseModel):
    name: str
    description: str
    url: str
    available: list[str]
    inputs: list[str]
    outputs: list[str]


class ToolchainStep(BaseModel):
    tool: str
    action: str
    passOutput: bool = False


class ToolchainRequest(BaseModel):
    sequence: list[ToolchainStep]
    data: dict[str, Any] = {}


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    sequence: list[ToolchainStep]


class Workflow(WorkflowCreate):
    id: str
    createdAt: str


class WorkflowExecuteRequest(BaseModel):
    data: dict[str, Any] = {}
