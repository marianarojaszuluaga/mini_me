"""
Project Brain read/reconciliation endpoints — ARCHITECTURE_JARVIS.md §5,
SPEC_JARVIS.md §6.1/§6.7. Event ingestion (acta -> decisionLog/alerts) already
lives in routers/projects.py's /brain/ingest-event; this router covers the
timeline + reconciliation surface that services/brain/* exposes.

# TODO: calibrar en implementacion — the parallel "brain" phase left no router
# on disk at all; this is the integration agent's fill-in wiring
# services/brain/ingest.py and services/brain/reconciliation.py (also written
# by the integration agent, see their headers) to real endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import authenticate_token
from app.services.brain import ingest, reconciliation

router = APIRouter(dependencies=[Depends(authenticate_token)])


@router.get("/projects/{project_id}/timeline")
async def get_timeline(project_id: str, days: int = Query(default=7, ge=1)) -> dict[str, Any]:
    events = ingest.list_recent_events(project_id, days)
    if events is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"projectId": project_id, "days": days, "events": events}


@router.get("/projects/{project_id}/reconciliation")
async def get_reconciliation(project_id: str) -> dict[str, Any]:
    result = reconciliation.get_latest(project_id)
    if result is None:
        # Distinguishes "project not found" (404) from "no run yet" (200,
        # empty) by checking existence separately.
        events = ingest.list_recent_events(project_id, days=1)
        if events is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"projectId": project_id, "gaps": [], "lastRunAt": None}
    return {"projectId": project_id, **result}


@router.post("/projects/{project_id}/reconciliation/run")
async def run_reconciliation(project_id: str) -> dict[str, Any]:
    result = await reconciliation.run_reconciliation(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"projectId": project_id, **result}
