"""
Manual/scheduled CLI entry point for app/services/obsidian_sync.py — see
that module's docstring for the full rationale (SPEC_JARVIS.md §11, item
3.1, and §15.1's 2026-08-21 fix).

Tarea 6 (2026-08-21): this now syncs from the REAL production API
(app.services.obsidian_sync.sync_to_obsidian_from_api), not local storage —
running this on Mariana's own machine reads her local dev filesystem, never
the real production Redis data, so a local sync must always go through the
deployed API to be real. This is the script meant to be run by a real
Windows Task Scheduler job on her machine (app/cron/sync_scheduler.py's
in-process scheduler doesn't survive Vercel's serverless recycling).

Usage:
    set OBSIDIAN_SYNC_BASE_URL=https://backmar-in-theinternet.vercel.app
    set OBSIDIAN_SYNC_API_KEY=<a real key from APP_API_KEYS>
    python scripts/sync_memories_to_obsidian.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.services.obsidian_sync import VAULT_DIR, sync_to_obsidian_from_api  # noqa: E402

_DEFAULT_BASE_URL = "https://backmar-in-theinternet.vercel.app"


async def main() -> None:
    base_url = os.environ.get("OBSIDIAN_SYNC_BASE_URL", _DEFAULT_BASE_URL)
    api_key = os.environ.get("OBSIDIAN_SYNC_API_KEY")
    if not api_key:
        print(
            "Error: falta OBSIDIAN_SYNC_API_KEY (una key real de APP_API_KEYS) "
            "como variable de entorno — nunca hardcodeada en este script."
        )
        sys.exit(1)

    counts = await sync_to_obsidian_from_api(base_url, api_key)
    print(
        f"Sincronizado desde {base_url}: {counts['mar_memory_entries']} entradas de Mar Memory, "
        f"{counts['projects']} proyectos -> {VAULT_DIR}"
    )


if __name__ == "__main__":
    asyncio.run(main())
