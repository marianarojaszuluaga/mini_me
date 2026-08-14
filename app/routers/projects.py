"""
GET /projects, GET /projects/{id}, POST /projects, POST /brain/ingest-event
(generalizes ingest-acta, accepts a "type" discriminator), and
POST /brain/ingest-acta kept as an alias calling the same handler with
type="acta" — migrated from server.js.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

from anthropic import AsyncAnthropic
from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.security import authenticate_token
from app.core.storage import get_storage
from app.schemas.project import ProjectCreateRequest
from app.services import agent_registry

router = APIRouter(dependencies=[Depends(authenticate_token)])


def _get_anthropic_client(settings: Settings = Depends(get_settings)) -> AsyncAnthropic:
    return AsyncAnthropic(**settings.anthropic_client_kwargs)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_project_brain() -> dict[str, Any]:
    return {"status": "pending", "decisionLog": [], "alerts": [], "meetingLog": []}


def _new_project_record(
    id_: str,
    name: str,
    owner: str | None,
    description: str | None,
    phase: int | None,
) -> dict[str, Any]:
    timestamp = _now_iso()
    return {
        "id": id_,
        "name": name,
        "owner": owner,
        "description": description,
        "currentPhase": phase or 1,
        "currentStep": "iniciando",
        "status": "active",
        "progress": 0,
        "createdAt": timestamp,
        "memory": {
            "projectBrain": _default_project_brain(),
            "backlogs": {
                "hu": {"status": "pending", "ids": []},
                "plans": {"status": "pending", "plans": []},
                "actas": {"status": "pending", "actas": []},
            },
            "sprints": {"current": 1, "status": "pending"},
            "timeline": {"createdAt": timestamp, "activities": []},
        },
        "repositories": [],
    }


def _ensure_brain_shape(project: dict[str, Any]) -> dict[str, Any]:
    """Projects created before decisionLog/alerts/meetingLog existed won't
    have them — backfill defensively rather than crashing on append."""
    memory = project.setdefault("memory", {})
    brain = memory.setdefault("projectBrain", {})
    brain.setdefault("decisionLog", [])
    brain.setdefault("alerts", [])
    brain.setdefault("meetingLog", [])
    return project


def _new_project_id() -> str:
    return f"Proyecto_{int(time.time() * 1000)}"


@router.get("/projects")
async def list_projects() -> list[dict[str, Any]]:
    storage = get_storage()
    return storage.read_projects()


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/projects", status_code=201)
async def create_project(body: ProjectCreateRequest) -> dict[str, Any]:
    storage = get_storage()
    new_project = _new_project_record(
        id_=_new_project_id(),
        name=body.name,
        owner=body.owner,
        description=body.description,
        phase=body.phase,
    )

    projects = storage.read_projects()
    projects.append(new_project)
    storage.write_projects(projects)

    return new_project


async def _ingest_event(
    client: AsyncAnthropic,
    event_type: str,
    project_name: str,
    content: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Generalizes ingest-acta: an event (acta, or any future event `type`)
    gets fed to Gabriela, who extracts decisions/alerts into the project's
    Brain. If no project matches `project_name` yet, one is created so the
    Brain still gets the entry."""
    if not project_name or not content:
        raise HTTPException(status_code=400, detail="projectName and content are required")

    metadata = metadata or {}
    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("name") == project_name), None)

    if not project:
        project = _new_project_record(
            id_=_new_project_id(),
            name=project_name,
            owner=metadata.get("attendees", "unknown"),
            description=f"Auto-creado desde evento ({event_type}): {metadata.get('meetingTitle', project_name)}",
            phase=None,
        )
        projects.append(project)

    _ensure_brain_shape(project)

    prompt = agent_registry.build_acta_ingest_prompt(content, metadata)
    model_config = agent_registry.get_model_config("gaby")
    response = await client.messages.create(
        model=model_config["model"],
        max_tokens=model_config["max_tokens"],
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text
    match = re.search(r"\{[\s\S]*\}", text)
    parsed = json.loads(match.group(0)) if match else {"decisions": [], "alerts": []}

    timestamp = _now_iso()
    source = metadata.get("docLink")

    for decision in parsed.get("decisions", []):
        project["memory"]["projectBrain"]["decisionLog"].append(
            {**decision, "timestamp": timestamp, "source": source}
        )
    for alert in parsed.get("alerts", []):
        project["memory"]["projectBrain"]["alerts"].append(
            {**alert, "timestamp": timestamp, "status": "open", "source": source}
        )
    project["memory"]["projectBrain"]["meetingLog"].append(
        {
            "timestamp": timestamp,
            "meetingTitle": metadata.get("meetingTitle"),
            "docLink": source,
            "date": metadata.get("date"),
        }
    )
    project["memory"]["projectBrain"]["status"] = "active"

    project.setdefault("memory", {}).setdefault("timeline", {}).setdefault("activities", []).append(
        {
            "timestamp": timestamp,
            "agent": "gaby",
            "action": f"evento '{event_type}' ingerido al Project Brain",
            "status": "completed",
        }
    )

    storage.write_projects(projects)

    return {
        "projectId": project["id"],
        "projectName": project["name"],
        "decisionsAdded": len(parsed.get("decisions", [])),
        "alertsAdded": len(parsed.get("alerts", [])),
        "brain": project["memory"]["projectBrain"],
    }


@router.post("/brain/ingest-event")
async def ingest_event(
    body: dict[str, Any] = Body(...),
    client: AsyncAnthropic = Depends(_get_anthropic_client),
) -> dict[str, Any]:
    event_type = body.get("type", "generic")
    project_name = body.get("projectName")
    # Accept either "content" (generalized) or "actaContent" (legacy shape)
    # so existing callers keep working without a payload change.
    content = body.get("content") or body.get("actaContent")
    metadata = body.get("metadata")
    return await _ingest_event(client, event_type, project_name, content, metadata)


@router.post("/brain/ingest-acta")
async def ingest_acta(
    body: dict[str, Any] = Body(...),
    client: AsyncAnthropic = Depends(_get_anthropic_client),
) -> dict[str, Any]:
    """Alias of /brain/ingest-event with type="acta", kept for backward
    compatibility with the existing "Proyecto Actas" Apps Script caller."""
    project_name = body.get("projectName")
    content = body.get("actaContent")
    metadata = body.get("metadata")
    return await _ingest_event(client, "acta", project_name, content, metadata)
