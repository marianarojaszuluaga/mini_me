"""
Vercel entrypoint — Python serverless functions.

Vercel's @vercel/python builder auto-detects a module-level ASGI `app`
variable in any api/*.py file and serves it directly (no WSGI/Mangum
adapter needed). This file just re-exports the real FastAPI app so every
request (see vercel.json's catch-all rewrite) is served by the same
single process that app/main.py already defines — MAP + Orchestrator +
Jarvis Mode all live in one FastAPI instance now, so there's no longer a
need for separate api/map.js + api/orchestrator.js entrypoints like the
Node version had.
"""

from app.main import app  # noqa: F401
