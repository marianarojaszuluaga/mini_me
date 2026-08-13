"""
Code<->spec reconciliation — Auditor comparing HU/AC claims of "done" against
real evidence (tests, PRs, commits), per ARCHITECTURE_JARVIS.md §5 and
SPEC_JARVIS.md §6.7/§10 ("nunca reporta 'cumple' sin evidencia; siempre
reporta 'sin test' cuando no hay evidencia").

# TODO: calibrar en implementacion — same fill-in as ingest.py: the parallel
# "brain" phase didn't land this module. `run_reconciliation` here is a real,
# working first pass: it reads the project's HU backlog ids and looks for a
# same-id mention in recent timeline activity as a coarse "has evidence"
# signal. The real version described in the spec (matching HU Acceptance
# Criteria against actual test files/PR content via the repo adapters) is a
# substantially bigger feature — this keeps the endpoint and metrics wiring
# real and functional today without inventing a fake "all good" result.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.storage import get_storage
from app.services.metrics.collector import record_reconciliation_run


def get_latest(project_id: str) -> dict[str, Any] | None:
    """Returns the project's last reconciliation result, or None if the
    project doesn't exist."""
    projects = get_storage().read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if project is None:
        return None
    return project.get("memory", {}).get("projectBrain", {}).get("reconciliation")


async def run_reconciliation(project_id: str) -> dict[str, Any] | None:
    """Runs a reconciliation pass for `project_id` and persists the result to
    project.memory.projectBrain.reconciliation. Returns the new reconciliation
    dict, or None if the project doesn't exist."""
    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if project is None:
        return None

    hu_ids = project.get("memory", {}).get("backlogs", {}).get("hu", {}).get("ids", [])
    activities = project.get("memory", {}).get("timeline", {}).get("activities", [])
    activity_text = " ".join(str(a.get("action", "")) for a in activities)

    gaps: list[dict[str, Any]] = []
    sin_test = 0
    for hu_id in hu_ids:
        has_evidence = hu_id in activity_text
        if not has_evidence:
            gaps.append(
                {
                    "huId": hu_id,
                    "claim": "done",
                    "evidence": None,
                    "status": "open",
                }
            )
            sin_test += 1

    previous = project.get("memory", {}).get("projectBrain", {}).get("reconciliation") or {}
    previous_open_ids = {g.get("huId") for g in previous.get("gaps", []) if g.get("status") == "open"}
    current_open_ids = {g["huId"] for g in gaps}
    gaps_closed_since_last = len(previous_open_ids - current_open_ids)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    reconciliation = {"lastRunAt": now, "gaps": gaps}

    project.setdefault("memory", {}).setdefault("projectBrain", {})["reconciliation"] = reconciliation
    storage.write_projects(projects)

    await record_reconciliation_run(
        project_id=project_id,
        gaps_found=len(gaps),
        gaps_closed_since_last=gaps_closed_since_last,
        sin_test=sin_test,
    )

    return reconciliation
