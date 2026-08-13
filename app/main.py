"""
FastAPI application entrypoint — replaces src/server.js.

CORS is left wide open (`allow_origins=["*"]`), matching the Express app's
bare `cors()` call with no restriction. FRONTEND_URL exists in settings for
whoever tightens this later.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import agents, brain, health, jarvis_chat, mar_memory, metrics, projects, repositories

settings = get_settings()

app = FastAPI(title="Orquestrador 360 — MAP Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# health.py has no auth dependency (deploy platforms probe it with no key).
app.include_router(health.router)

# agents.py: /agents, /phases, /phases/{id_or_key}, /agents/{name}/invoke,
# /orchestrate, /evaluate — all behind the auth dependency.
app.include_router(agents.router)

# projects.py: /projects, /projects/{id}, /brain/ingest-event,
# /brain/ingest-acta — all behind the auth dependency.
app.include_router(projects.router)

# mar_memory.py: GET/POST /mar/memory, DELETE /mar/memory/{id} — behind the
# auth dependency (SPEC_JARVIS.md §6.3, §6.5).
app.include_router(mar_memory.router)

# jarvis_chat.py: POST /jarvis/chat — the conversational agentic loop
# (ARCHITECTURE_JARVIS.md §2, HU-006-JarvisMode) — behind the auth dependency.
app.include_router(jarvis_chat.router)

# repositories.py: /auth-profiles, /projects/{id}/repositories — repo
# connections + Auth Profiles (SPEC_JARVIS.md §6.1/§6.2) — behind auth.
app.include_router(repositories.router)

# brain.py: /projects/{id}/timeline, /projects/{id}/reconciliation[/run] —
# Project Brain timeline + reconciliation (ARCHITECTURE_JARVIS.md §5) — behind auth.
app.include_router(brain.router)

# metrics.py: /metrics/* — Analytics/Metrics read surface
# (ARCHITECTURE_JARVIS.md §4/§7, HU-008/009/010-JarvisMode) — behind auth.
app.include_router(metrics.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
