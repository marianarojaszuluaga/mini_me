"""GET /health — unauthenticated on purpose, same as the Express app: deploy
platforms (Railway, Render, Vercel, ...) probe this over plain HTTP with no
API key to decide whether to route traffic to the instance."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    storage = get_storage()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "environment": settings.environment,
        "storage": "vercel-kv" if storage.using_kv else "filesystem",
    }
