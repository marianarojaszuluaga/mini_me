"""
Velocity/Speed/Rollover/Completion endpoints (Tarea 2, PLAN CTO QA/KPI
2026-09-10). See app/schemas/velocity.py for the data model and why
completed_items is a manual PM input while the reconciliation-derived line
is not.

Protected with `authenticate_api_key_or_user` — same dependency as
projects.py/repositories.py — so this works with a user JWT, not only an
API key (the exact bug fixed 2026-09-09 for other routers).
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import authenticate_api_key_or_user
from app.core.storage import get_storage
from app.schemas.velocity import VelocitySeries, WeeklyCommitment, WeeklyVelocityPoint
from app.services.metrics import collector

router = APIRouter(dependencies=[Depends(authenticate_api_key_or_user)])

_COMMITMENTS_SERIES = "velocity-weekly-commitments"


def _week_key(project_id: str, week_start: date_type) -> str:
    return f"{project_id}:{week_start.isoformat()}"


@router.post("/projects/{project_id}/velocity/commitments")
async def register_commitment(project_id: str, commitment: WeeklyCommitment) -> dict:
    """Registers (or updates) one week's commitment. Idempotent on
    (project_id, week_start): posting the same week twice updates that row
    in place instead of appending a duplicate."""
    if commitment.project_id != project_id:
        raise HTTPException(status_code=400, detail="project_id en el body no coincide con la URL")

    storage = get_storage()
    rows = storage.read_series(_COMMITMENTS_SERIES)
    key = _week_key(project_id, commitment.week_start)

    updated = False
    new_rows = []
    for row in rows:
        if _week_key(row["project_id"], date_type.fromisoformat(row["week_start"])) == key:
            new_rows.append(commitment.model_dump(mode="json"))
            updated = True
        else:
            new_rows.append(row)
    if not updated:
        new_rows.append(commitment.model_dump(mode="json"))

    storage.write_series(_COMMITMENTS_SERIES, new_rows)
    return {"ok": True, "updated_existing": updated, "commitment": commitment.model_dump(mode="json")}


@router.get("/projects/{project_id}/velocity")
async def get_velocity(project_id: str) -> VelocitySeries:
    """Returns the velocity series for a project: weekly velocity,
    rollover, completion rate, plus the reconciliation-derived 3rd line
    (gaps_found/gaps_closed) matched by week bucket."""
    storage = get_storage()
    rows = [
        row
        for row in storage.read_series(_COMMITMENTS_SERIES)
        if row.get("project_id") == project_id
    ]
    rows.sort(key=lambda r: r["week_start"])

    reconciliation_runs = [
        run for run in collector.read_reconciliation_runs() if run.get("project_id") == project_id
    ]

    points: list[WeeklyVelocityPoint] = []
    for row in rows:
        week_start = date_type.fromisoformat(row["week_start"])
        committed = row["committed_items"]
        completed = row.get("completed_items")

        rollover = max(committed - completed, 0) if completed is not None else 0
        completion_rate = (completed / committed) if (completed is not None and committed > 0) else None
        velocity = completed

        # Match reconciliation runs whose date falls within this ISO week.
        week_runs = [
            run
            for run in reconciliation_runs
            if _iso_week_start(run["date"][:10]) == week_start
        ]
        gaps_found = sum(r.get("gaps_found", 0) for r in week_runs) if week_runs else None
        gaps_closed = sum(r.get("gaps_closed_since_last", 0) for r in week_runs) if week_runs else None

        points.append(
            WeeklyVelocityPoint(
                week_start=week_start,
                committed_items=committed,
                completed_items=completed,
                velocity=velocity,
                rollover=rollover,
                completion_rate=completion_rate,
                reconciliation_gaps_found=gaps_found,
                reconciliation_gaps_closed=gaps_closed,
            )
        )

    return VelocitySeries(project_id=project_id, points=points)


def _iso_week_start(iso_date_str: str) -> date_type:
    d = date_type.fromisoformat(iso_date_str)
    return d.fromordinal(d.toordinal() - d.weekday())
