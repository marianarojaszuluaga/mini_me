"""
Timeline ingestion — recent raw activity events per project.

# TODO: calibrar en implementacion — the parallel "brain" phase left only the
# package docstring on disk (services/brain/__init__.py), no ingest.py or
# reconciliation.py. This is the integration agent's fill-in, matching the
# shape jarvis_chat/tools.py's read_timeline already assumed as the eventual
# real import (see the TODO there): a thin, real function over
# project.memory.timeline.activities, not a stub.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.storage import get_storage


def list_recent_events(project_id: str, days: int = 7) -> list[dict[str, Any]] | None:
    """Returns the project's recent timeline activities within the last
    `days` days, or None if the project doesn't exist."""
    projects = get_storage().read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if project is None:
        return None

    activities = project.get("memory", {}).get("timeline", {}).get("activities", [])
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400

    def _within_window(activity: dict[str, Any]) -> bool:
        ts = activity.get("timestamp")
        if not ts:
            return True
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return True
        return parsed.timestamp() >= cutoff

    return [a for a in activities if _within_window(a)]


def record_event(project_id: str, agent: str | None, action: str, status: str = "completed") -> dict[str, Any] | None:
    """Appends one activity event to a project's timeline. Returns the
    appended event, or None if the project doesn't exist."""
    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if project is None:
        return None

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "agent": agent,
        "action": action,
        "status": status,
    }
    project.setdefault("memory", {}).setdefault("timeline", {}).setdefault("activities", []).append(event)
    storage.write_projects(projects)
    return event
