"""
GET/POST /mar/memory, DELETE /mar/memory/{id} — Memoria de Mar
(SPEC_JARVIS.md §6.3, §6.5, HU-007-JarvisMode). System-level (not
per-project): what Mar understands about the system, open questions, and
corrections she's made to Jarvis's assumptions.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import authenticate_token
from app.schemas.mar_memory import MarMemoryEntry, MarMemoryWriteRequest
from app.services import mar_memory

router = APIRouter(dependencies=[Depends(authenticate_token)])


@router.get("/mar/memory")
async def list_mar_memory() -> list[dict[str, Any]]:
    return mar_memory.get_all_entries()


@router.post("/mar/memory", status_code=201)
async def write_mar_memory(body: MarMemoryWriteRequest) -> dict[str, Any]:
    entry = MarMemoryEntry(
        **({"id": body.id} if body.id else {}),
        type=body.type,
        content=body.content,
        source=body.source,
    )
    return mar_memory.add_or_update_entry(entry)


@router.delete("/mar/memory/{entry_id}")
async def delete_mar_memory(entry_id: str) -> dict[str, Any]:
    deleted = mar_memory.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mar memory entry not found")
    return {"deleted": True, "id": entry_id}
