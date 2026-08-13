"""
GET/POST /changelog, POST /changelog/{id}/approve — system-improvement
changelog (SPEC_JARVIS.md §10, HU-009-JarvisMode). Feeds "Analítica completa"
→ "Changelog de mejoras" (HU-010).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import authenticate_token
from app.schemas.changelog import ChangelogCreateRequest
from app.services import changelog

router = APIRouter(dependencies=[Depends(authenticate_token)])


@router.get("/changelog")
async def list_changelog() -> list[dict[str, Any]]:
    return changelog.list_entries()


@router.post("/changelog", status_code=201)
async def create_changelog_proposal(body: ChangelogCreateRequest) -> dict[str, Any]:
    return changelog.create_proposal(
        agent_name=body.agent_name,
        what_changed=body.what_changed,
        reason=body.reason,
        before_window=body.before_window,
    )


@router.get("/changelog/{entry_id}")
async def get_changelog_entry(entry_id: str) -> dict[str, Any]:
    entry = changelog.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Changelog entry not found")
    # Trigger a fresh after_scores read whenever a caller looks at the
    # detail view — cheap (in-memory aggregation) and keeps "en progreso"
    # entries up to date without a separate background job dependency.
    refreshed = changelog.compute_after_scores(entry_id)
    return refreshed or entry


@router.post("/changelog/{entry_id}/approve")
async def approve_changelog_entry(entry_id: str) -> dict[str, Any]:
    entry = changelog.approve_proposal(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Changelog entry not found")
    return entry
