"""
WORKFLOWS — save and execute tool sequences. Migrated from src/orchestrator.js's
GET/POST /workflows handlers. CRUD goes through app/core/storage.py's
read_workflows/write_workflows (already present there, same as store.js's
readWorkflows/writeWorkflows).
"""

from __future__ import annotations

import time
from typing import Any

from app.core.storage import get_storage
from app.schemas.orchestrator import Workflow, WorkflowCreate


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def list_workflows() -> list[dict[str, Any]]:
    return get_storage().read_workflows()


def get_workflow(workflow_id: str) -> dict[str, Any] | None:
    return next((w for w in list_workflows() if w.get("id") == workflow_id), None)


def create_workflow(payload: WorkflowCreate) -> dict[str, Any]:
    workflow = Workflow(
        id=f"workflow_{int(time.time() * 1000)}",
        name=payload.name,
        description=payload.description,
        sequence=payload.sequence,
        createdAt=_now(),
    )
    workflow_dict = workflow.model_dump()

    storage = get_storage()
    workflows = storage.read_workflows()
    workflows.append(workflow_dict)
    storage.write_workflows(workflows)

    return workflow_dict
