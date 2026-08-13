"""
Manual CLI entry point for app/services/obsidian_sync.py — see that module's
docstring for the full rationale (SPEC_JARVIS.md §11, item 3.1).

As of 2026-08-14 this same sync also runs automatically every 3h as part of
app/cron/sync_scheduler.py's existing daytime job — this script remains for
running it on demand (e.g. right after seeding real Mar Memory entries, to
see the result immediately instead of waiting for the next cron tick).

Usage:
    python scripts/sync_memories_to_obsidian.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.services.obsidian_sync import VAULT_DIR, sync_to_obsidian  # noqa: E402


def main() -> None:
    counts = sync_to_obsidian()
    print(
        f"Sincronizado: {counts['mar_memory_entries']} entradas de Mar Memory, "
        f"{counts['projects']} proyectos -> {VAULT_DIR}"
    )


if __name__ == "__main__":
    main()
