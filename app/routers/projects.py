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
from app.core.security import authenticate_api_key_or_user
from app.core.storage import get_storage
from app.schemas.auth_profile import AuthProfile
from app.schemas.basecamp_publication import BasecampPublication
from app.schemas.project import BasecampMirror, ProjectCreateRequest
from app.schemas.user import User
from app.services import agent_registry
from app.services.auth_service import get_current_user_optional
from app.schemas.basecamp_nomenclature import BasecampNomenclatureRule
from app.services.basecamp_client import (
    BasecampError,
    create_card,
    get_active_sprint,
    get_card_table_snapshot,
    list_basecamp_projects,
    list_card_tables,
    list_categories,
    list_people,
    move_card,
    update_card,
)
from app.services.basecamp_nomenclature import (
    Card as NomenclatureCard,
)
from app.services.basecamp_nomenclature import (
    audit_card_tables,
    looks_spanish,
    suggest_translation,
)
from app.services.basecamp_publisher import _PUBLICATIONS_SERIES, _rebuild_payload, retry_publication
from app.services.project_scaffold import scaffold_project_repo, write_phase_artifact

router = APIRouter(dependencies=[Depends(authenticate_api_key_or_user)])


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


def _get_owned_project(
    projects: list[dict[str, Any]],
    project_id: str,
    current_user: User | None,
) -> dict[str, Any]:
    """Same ownership rule as GET /projects/{id}: a project with an
    owner_user_id is only visible to that owner once a real user JWT is
    present; API-key-only callers (current_user is None) keep seeing
    everything, so server-to-server calls don't break."""
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user is not None and project.get("owner_user_id") not in (
        None,
        current_user.id,
    ):
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects")
async def list_projects(
    current_user: User | None = Depends(get_current_user_optional),
) -> list[dict[str, Any]]:
    storage = get_storage()
    projects = storage.read_projects()
    # Multi-usuario (2026-09-09): when a real user JWT is present, only that
    # user's own projects are returned. A project with no owner_user_id
    # (pre-migration data) is only visible to API-key-only callers, not
    # filtered into any one user's list — see PLAN-i18n-multiusuario.md's
    # migration seed, which backfills these for Mariana's existing data.
    if current_user is not None:
        projects = [p for p in projects if p.get("owner_user_id") == current_user.id]
    return projects


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user is not None and project.get("owner_user_id") not in (
        None,
        current_user.id,
    ):
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/projects", status_code=201)
async def create_project(
    body: ProjectCreateRequest,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    storage = get_storage()
    new_project = _new_project_record(
        id_=_new_project_id(),
        name=body.name,
        owner=body.owner,
        description=body.description,
        phase=body.phase,
    )
    if current_user is not None:
        new_project["owner_user_id"] = current_user.id

    projects = storage.read_projects()
    projects.append(new_project)
    storage.write_projects(projects)

    return new_project


@router.delete("/projects/{project_id}", status_code=200)
async def delete_project(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Soft delete (Mariana, 2026-08-19): sets status="archived" instead of
    removing the record — real data is never dropped, and this is
    reversible (re-activate by setting status back to "active" via a
    future un-archive action). The frontend gates this behind a real
    confirmation modal (type-to-confirm the project name) and filters
    archived projects out of the main Proyectos grid."""
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    project["status"] = "archived"
    storage.write_projects(projects)
    return project


@router.post("/projects/{project_id}/scaffold")
async def scaffold_project(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """TAREA A (onboarding, 2026-09-11): writes the standard 6-folder project
    structure (01-Planning..06-FollowUp, each with a placeholder README.md)
    into the project's first connected repo, reusing the existing
    GitHub/Bitbucket adapters (project_scaffold.scaffold_project_repo)."""
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    repositories = project.get("repositories", [])
    if not repositories:
        raise HTTPException(status_code=400, detail="Project has no connected repository")

    repository = repositories[0]
    auth_profiles = storage.read_auth_profiles()
    try:
        written = await scaffold_project_repo(repository, auth_profiles)
    except Exception as error:  # noqa: BLE001 - surfaced as a clean 502, not a 500
        raise HTTPException(status_code=502, detail=f"Failed to write scaffold: {error}") from error

    timestamp = _now_iso()
    project.setdefault("memory", {}).setdefault("timeline", {}).setdefault("activities", []).append(
        {
            "timestamp": timestamp,
            "agent": "scaffold",
            "action": "Aplicó estructura estándar de carpetas (01-Planning..06-FollowUp)",
            "status": "completed",
        }
    )
    storage.write_projects(projects)

    return {
        "projectId": project_id,
        "repository": {"owner": repository.get("owner"), "repo": repository.get("repo")},
        "filesWritten": written,
    }


@router.post("/projects/{project_id}/phase-artifact")
async def upload_phase_artifact(
    project_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """TAREA B, pieza 7 ("Subir a repo"): commits one user-activated agent
    result into the phase's mapped folder (project_scaffold.PHASE_KEY_TO_FOLDER)
    of the project's first connected repo. The frontend only calls this
    after the person explicitly clicked "Activar" on a result — never
    automatically."""
    phase = body.get("phase")
    filename = body.get("filename")
    content = body.get("content")
    if not (phase and filename and content):
        raise HTTPException(status_code=400, detail="phase, filename and content are required")

    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    repositories = project.get("repositories", [])
    if not repositories:
        raise HTTPException(status_code=400, detail="Project has no connected repository")

    auth_profiles = storage.read_auth_profiles()
    try:
        path = await write_phase_artifact(repositories[0], auth_profiles, phase, filename, content)
    except Exception as error:  # noqa: BLE001 - surfaced as a clean 502, not a 500
        raise HTTPException(status_code=502, detail=f"Failed to write phase artifact: {error}") from error

    return {"projectId": project_id, "path": path}


@router.put("/projects/{project_id}/basecamp")
async def link_basecamp_project(
    project_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Links (or re-links) this project to a real Basecamp project —
    account_id + project_id, e.g. from https://3.basecamp.com/{account_id}/
    projects/{project_id}. Real link only: does not verify access against
    the Basecamp API here (that needs a connected Auth Profile's token,
    which the caller may not have yet) — a genuinely broken link surfaces
    when something actually tries to read from it, not fabricated here."""
    account_id = body.get("account_id")
    project_ref = body.get("project_id")
    if not account_id or not project_ref:
        raise HTTPException(status_code=400, detail="account_id and project_id are required")

    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    project["basecamp"] = {"account_id": str(account_id), "project_id": str(project_ref)}
    storage.write_projects(projects)
    return project


@router.delete("/projects/{project_id}/basecamp")
async def unlink_basecamp_project(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    project["basecamp"] = None
    storage.write_projects(projects)
    return project


def _get_basecamp_auth_profile(storage: Any, account_id: str) -> AuthProfile:
    """Shared lookup — same real matching rule already used by
    get_project_sprint: a Basecamp Auth Profile scoped to this exact
    account_id, never fabricated."""
    profiles = storage.read_auth_profiles()
    profile_dict = next(
        (
            p
            for p in profiles
            if p.get("provider") == "basecamp" and p.get("scope") == f"account_id:{account_id}"
        ),
        None,
    )
    if not profile_dict:
        raise HTTPException(
            status_code=501,
            detail=f"No hay un Auth Profile de Basecamp conectado para la cuenta {account_id}.",
        )
    return AuthProfile(**profile_dict)


@router.get("/auth-profiles/{profile_id}/basecamp-projects")
async def list_basecamp_projects_for_profile(profile_id: str) -> list[dict[str, Any]]:
    """Real Basecamp projects for this Auth Profile's account — Tarea 2 Gap 3
    (2026-08-21): lets "Vincular Basecamp" show a real picker instead of
    account_id/project_id typed by hand."""
    storage = get_storage()
    profiles = storage.read_auth_profiles()
    profile_dict = next((p for p in profiles if p.get("id") == profile_id), None)
    if not profile_dict:
        raise HTTPException(status_code=404, detail="Auth profile not found")
    if profile_dict.get("provider") != "basecamp":
        raise HTTPException(status_code=400, detail="Este Auth Profile no es de Basecamp.")

    scope = profile_dict.get("scope") or ""
    if not scope.startswith("account_id:"):
        raise HTTPException(status_code=400, detail="Este Auth Profile no tiene un account_id real en su scope.")
    account_id = scope.split(":", 1)[1]

    auth_profile = AuthProfile(**profile_dict)
    try:
        return await list_basecamp_projects(auth_profile, account_id)
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/projects/{project_id}/basecamp-card-tables")
async def list_project_card_tables(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> list[dict[str, Any]]:
    """Real Card Tables of the linked Basecamp project — Tarea 2 Gap 3
    corrección: nunca el todolist, siempre Card Tables reales listadas para
    que la usuaria elija una o varias."""
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    basecamp = project.get("basecamp")
    if not basecamp:
        raise HTTPException(status_code=501, detail="Este proyecto no tiene un proyecto de Basecamp vinculado.")

    account_id = str(basecamp["account_id"])
    auth_profile = _get_basecamp_auth_profile(storage, account_id)
    try:
        return await list_card_tables(auth_profile, account_id, str(basecamp["project_id"]))
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.put("/projects/{project_id}/basecamp-card-tables")
async def set_project_card_tables(
    project_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Saves which Card Table(s) the usuaria elegió as the real sprint
    source — never assumed automatically."""
    card_table_ids = body.get("cardTableIds")
    if not isinstance(card_table_ids, list):
        raise HTTPException(status_code=400, detail="cardTableIds (list) is required")

    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    if not project.get("basecamp"):
        raise HTTPException(status_code=501, detail="Este proyecto no tiene un proyecto de Basecamp vinculado.")

    project["basecamp"]["selectedCardTableIds"] = [str(i) for i in card_table_ids]
    storage.write_projects(projects)
    return project


@router.get("/projects/{project_id}/basecamp-mirror")
async def get_project_basecamp_mirror(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Real espejo del proyecto de Basecamp (Tarea 2 Gap 3) — nombre/
    descripción + columnas/cards reales de las Card Tables elegidas.
    501 explícito si falta el link, el Auth Profile, o no se eligió ninguna
    Card Table todavía — nunca inventa un espejo vacío como si fuera real."""
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    basecamp = project.get("basecamp")
    if not basecamp:
        raise HTTPException(status_code=501, detail="Este proyecto no tiene un proyecto de Basecamp vinculado.")

    account_id = str(basecamp["account_id"])
    real_project_id = str(basecamp["project_id"])
    selected_ids = basecamp.get("selectedCardTableIds") or []
    if not selected_ids:
        raise HTTPException(
            status_code=501,
            detail="Este proyecto no tiene ninguna Card Table elegida como fuente de sprint todavía.",
        )

    auth_profile = _get_basecamp_auth_profile(storage, account_id)
    try:
        bc_projects = await list_basecamp_projects(auth_profile, account_id)
        bc_project = next((p for p in bc_projects if p["id"] == real_project_id), None)
        card_tables = [
            await get_card_table_snapshot(auth_profile, account_id, real_project_id, card_table_id)
            for card_table_id in selected_ids
        ]
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    mirror = BasecampMirror(
        name=bc_project.get("name") if bc_project else None,
        description=bc_project.get("description") if bc_project else None,
        cardTables=card_tables,
        lastSyncAt=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

    project.setdefault("memory", {})["basecampMirror"] = mirror.model_dump(mode="json")
    storage.write_projects(projects)
    return mirror.model_dump(mode="json")


@router.get("/projects/{project_id}/sprint")
async def get_project_sprint(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Real sprint (active Basecamp to-do list) for a linked project — Fase E
    of the mockup-fidelity plan. 501 if there's nothing real to read yet
    (no Basecamp link, or no matching Basecamp Auth Profile with a real
    OAuth token) — never a fabricated sprint."""
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    basecamp = project.get("basecamp")
    if not basecamp:
        raise HTTPException(status_code=501, detail="Este proyecto no tiene un proyecto de Basecamp vinculado.")

    account_id = str(basecamp["account_id"])
    profiles = storage.read_auth_profiles()
    profile_dict = next(
        (
            p
            for p in profiles
            if p.get("provider") == "basecamp" and p.get("scope") == f"account_id:{account_id}"
        ),
        None,
    )
    if not profile_dict:
        raise HTTPException(
            status_code=501,
            detail=f"No hay un Auth Profile de Basecamp conectado para la cuenta {account_id}.",
        )

    auth_profile = AuthProfile(**profile_dict)
    try:
        sprint = await get_active_sprint(auth_profile, account_id, str(basecamp["project_id"]))
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return sprint


_DEFAULT_PUBLISH_CONFIG = {
    "enabled": False,
    "publish_on_start": True,
    "publish_on_close": True,
    "category_id": None,
    "notify_person_ids": [],
}


@router.get("/projects/{project_id}/basecamp-publish")
async def get_basecamp_publish_config(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    config = (project.get("basecamp") or {}).get("publish") or {}
    return {**_DEFAULT_PUBLISH_CONFIG, **config}


@router.put("/projects/{project_id}/basecamp-publish")
async def set_basecamp_publish_config(
    project_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """HU-043 E-1 — valida `category_id` contra las categorías reales del
    Message Board antes de guardar; un id inventado/de otro proyecto nunca
    se persiste en silencio."""
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    basecamp = project.get("basecamp")
    if not basecamp:
        raise HTTPException(status_code=501, detail="Este proyecto no tiene un proyecto de Basecamp vinculado.")

    category_id = body.get("category_id")
    if category_id is not None:
        account_id = str(basecamp["account_id"])
        auth_profile = _get_basecamp_auth_profile(storage, account_id)
        try:
            categories = await list_categories(auth_profile, account_id, str(basecamp["project_id"]))
        except BasecampError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        if not any(c["id"] == str(category_id) for c in categories):
            raise HTTPException(
                status_code=400,
                detail=f"category_id {category_id} no existe en las categorías reales de este Message Board.",
            )

    config = {**_DEFAULT_PUBLISH_CONFIG, **(basecamp.get("publish") or {}), **body}
    basecamp["publish"] = config
    storage.write_projects(projects)
    return config


@router.get("/projects/{project_id}/sprints/{sprint_id}/publications")
async def list_sprint_publications(
    project_id: str,
    sprint_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> list[dict[str, Any]]:
    """§4a — "sprint_id" acá ES el id de la Card Table ya seleccionada
    (Project.basecamp.selectedCardTableIds), no un dominio de Sprint propio
    (no existe todavía en este stack). Se anexa a projects.py en vez de un
    router de sprints separado porque no hay nada más que un Sprint pudiera
    exponer en este stack.

    Dispara el reintento perezoso (plan §1.1 Opción A, sin cola/cron): cada
    publicación `pending` de este sprint cuyo backoff ya elapsó se reintenta
    acá mismo antes de responder — este endpoint es el que la UI poll-ea."""
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)

    basecamp = project.get("basecamp") or {}
    account_id = basecamp.get("account_id")
    auth_profile = _get_basecamp_auth_profile(storage, str(account_id)) if account_id else None

    rows = storage.read_series(_PUBLICATIONS_SERIES)
    result: list[dict[str, Any]] = []
    for row in rows:
        if row.get("sprint_id") != sprint_id:
            continue
        if row.get("status") == "pending" and auth_profile is not None:
            payload = _rebuild_payload(row, project)
            if payload is not None:
                try:
                    publication = await retry_publication(row["id"], auth_profile, project, payload)
                    result.append(publication.model_dump(mode="json"))
                    continue
                except BasecampError:
                    pass  # el reintento perezoso no puede tumbar el GET — se devuelve el estado tal cual
        result.append(row)
    return result


@router.post("/publications/{publication_id}/retry")
async def retry_basecamp_publication(
    publication_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """HU-045 CA-6 — idempotente: si ya está `sent`, 200 sin reintentar
    (retry_publication ya es no-op en ese caso, así que solo hace falta
    resolver auth_profile/project reales para el caso que sí reintenta)."""
    storage = get_storage()
    rows = storage.read_series(_PUBLICATIONS_SERIES)
    row = next((r for r in rows if r.get("id") == publication_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Publication not found")

    if row.get("status") == "sent":
        return row

    projects = storage.read_projects()
    project = _get_owned_project(projects, row.get("project_id"), current_user)

    basecamp = project.get("basecamp") or {}
    account_id = basecamp.get("account_id")
    if not account_id:
        raise HTTPException(status_code=501, detail="Este proyecto no tiene un proyecto de Basecamp vinculado.")
    auth_profile = _get_basecamp_auth_profile(storage, str(account_id))

    payload = _rebuild_payload(row, project)
    if payload is None:
        raise HTTPException(
            status_code=501, detail="Este proyecto no tiene memoria de sprint suficiente para reintentar."
        )

    try:
        publication = await retry_publication(publication_id, auth_profile, project, payload)
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return publication.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Autobasecamp — SPEC_AUTOBASECAMP.md §4.3. Todo reusa _get_basecamp_auth_profile
# / _get_owned_project — mismo Auth Profile, misma regla de ownership que el
# resto de este router; ningún token nuevo.
# ---------------------------------------------------------------------------


def _project_basecamp_or_501(project: dict[str, Any]) -> dict[str, Any]:
    basecamp = project.get("basecamp")
    if not basecamp:
        raise HTTPException(status_code=501, detail="Este proyecto no tiene un proyecto de Basecamp vinculado.")
    return basecamp


@router.post("/projects/{project_id}/basecamp-card-tables/{table_id}/cards")
async def create_basecamp_card(
    project_id: str,
    table_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """§4.3 — crea una card en la columna (`list_id`) indicada del Card
    Table `table_id`. `list_id` es el id de la columna dentro de la tabla,
    tomado del snapshot ya pintado en el UI."""
    list_id = body.get("list_id")
    title = body.get("title")
    if not list_id or not title:
        raise HTTPException(status_code=400, detail="list_id y title son requeridos")

    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    basecamp = _project_basecamp_or_501(project)

    account_id = str(basecamp["account_id"])
    auth_profile = _get_basecamp_auth_profile(storage, account_id)
    try:
        return await create_card(
            auth_profile,
            account_id,
            str(basecamp["project_id"]),
            str(list_id),
            title,
            content_html=body.get("content"),
            due_on=body.get("due_on"),
            assignee_ids=body.get("assignee_ids"),
        )
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.put("/projects/{project_id}/basecamp-cards/{card_id}")
async def update_basecamp_card(
    project_id: str,
    card_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    basecamp = _project_basecamp_or_501(project)

    account_id = str(basecamp["account_id"])
    auth_profile = _get_basecamp_auth_profile(storage, account_id)
    try:
        return await update_card(
            auth_profile,
            account_id,
            str(basecamp["project_id"]),
            card_id,
            title=body.get("title"),
            content_html=body.get("content"),
            due_on=body.get("due_on"),
        )
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/projects/{project_id}/basecamp-cards/{card_id}/move")
async def move_basecamp_card(
    project_id: str,
    card_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    target_list_id = body.get("target_list_id")
    if not target_list_id:
        raise HTTPException(status_code=400, detail="target_list_id es requerido")

    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    basecamp = _project_basecamp_or_501(project)

    account_id = str(basecamp["account_id"])
    auth_profile = _get_basecamp_auth_profile(storage, account_id)
    try:
        return await move_card(auth_profile, account_id, str(basecamp["project_id"]), card_id, str(target_list_id))
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/projects/{project_id}/basecamp-people")
async def list_basecamp_people(
    project_id: str,
    current_user: User | None = Depends(get_current_user_optional),
) -> list[dict[str, Any]]:
    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    basecamp = _project_basecamp_or_501(project)

    account_id = str(basecamp["account_id"])
    auth_profile = _get_basecamp_auth_profile(storage, account_id)
    try:
        return await list_people(auth_profile, account_id, str(basecamp["project_id"]))
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/basecamp-nomenclature-rules")
async def list_basecamp_nomenclature_rules(account_id: str) -> list[dict[str, Any]]:
    """§4.3 — reglas de rango de nomenclatura, a nivel de cuenta de
    Basecamp (§7.1: no por proyecto de Minime; cada rule ya es
    per-card_table_key, lo que da independencia por cliente/proyecto)."""
    storage = get_storage()
    rules = storage.read_basecamp_nomenclature_rules()
    return [r for r in rules if r.get("account_id") == account_id]


@router.put("/basecamp-nomenclature-rules/{card_table_key}")
async def upsert_basecamp_nomenclature_rule(
    card_table_key: str,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Crea/edita una regla de rango. Valida solapamiento de rangos con
    otras tablas de la misma cuenta (§5.3) — advierte, no bloquea: guarda
    igual pero devuelve `overlap_warnings` para que el UI lo muestre antes
    de confiar en el resultado."""
    body = {**body, "card_table_key": card_table_key}
    try:
        rule = BasecampNomenclatureRule(**body)
    except Exception as error:  # noqa: BLE001 - surfaced as a clean 400, not a 500
        raise HTTPException(status_code=400, detail=f"Regla inválida: {error}") from error

    storage = get_storage()
    rules = storage.read_basecamp_nomenclature_rules()
    others = [r for r in rules if r.get("account_id") == rule.account_id and r.get("card_table_key") != card_table_key]

    overlap_warnings = []
    for other in others:
        other_ranges = other.get("reserved_ranges") or []
        for start, end in rule.reserved_ranges:
            for other_start, other_end in other_ranges:
                if start <= other_end and other_start <= end:
                    overlap_warnings.append(
                        f"Rango ({start},{end}) se solapa con '{other.get('label')}' ({other_start},{other_end})."
                    )

    rules = [r for r in rules if r.get("card_table_key") != card_table_key]
    rules.append(rule.model_dump(mode="json"))
    storage.write_basecamp_nomenclature_rules(rules)

    return {**rule.model_dump(mode="json"), "overlap_warnings": overlap_warnings}


@router.post("/projects/{project_id}/basecamp-nomenclature-audit")
async def run_basecamp_nomenclature_audit(
    project_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """§4.3 / §7.1 — opera SOLO sobre los `card_table_ids` explícitamente
    pasados en el body; nunca cruza automáticamente con Card Tables de
    otros proyectos/clientes aunque compartan cuenta."""
    card_table_ids = body.get("card_table_ids")
    if not isinstance(card_table_ids, list) or not card_table_ids:
        raise HTTPException(status_code=400, detail="card_table_ids (lista no vacía) es requerido")

    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    basecamp = _project_basecamp_or_501(project)

    account_id = str(basecamp["account_id"])
    real_project_id = str(basecamp["project_id"])
    auth_profile = _get_basecamp_auth_profile(storage, account_id)

    all_rules = [BasecampNomenclatureRule(**r) for r in storage.read_basecamp_nomenclature_rules() if r.get("account_id") == account_id]

    cards_by_table: dict[str, list[NomenclatureCard]] = {}
    try:
        for table_id in card_table_ids:
            table_id = str(table_id)
            snapshot = await get_card_table_snapshot(auth_profile, account_id, real_project_id, table_id)
            card_table_key = f"{real_project_id}:{table_id}"
            cards: list[NomenclatureCard] = []
            for column in snapshot.get("columns", []):
                for card in column.get("cards", []):
                    cards.append(
                        NomenclatureCard(
                            id=str(card.get("id", card.get("title", ""))),
                            title=card.get("title", ""),
                            card_table_key=card_table_key,
                            url=card.get("url"),
                        )
                    )
            cards_by_table[card_table_key] = cards
    except BasecampError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    result = audit_card_tables(cards_by_table, all_rules)

    # §7.3 — traducción ES->EN opcional, solo si la tabla de la card la
    # tiene prendida (translate_to_english=True). Best-effort: nunca rompe
    # el audit si el LLM falla.
    rules_by_key = {r.card_table_key: r for r in all_rules}
    for finding in [*result.duplicates, *result.missing]:
        rule = rules_by_key.get(finding.card.card_table_key)
        if rule and rule.translate_to_english:
            text = finding.suggested_title or finding.card.title
            if looks_spanish(text):
                finding.suggested_translation = await suggest_translation(text)

    return result.model_dump(mode="json")


@router.post("/projects/{project_id}/basecamp-nomenclature-audit/apply")
async def apply_basecamp_nomenclature_fixes(
    project_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Aplica una selección explícita de `{card_id, new_title}` — nunca
    todo por default (§5.2). Batch con manejo de error por-card: una card
    que falla no aborta el resto, y el resultado lista éxitos/fallos
    reales, nunca fabricados."""
    fixes = body.get("fixes")
    if not isinstance(fixes, list) or not fixes:
        raise HTTPException(status_code=400, detail="fixes (lista no vacía de {card_id, new_title}) es requerido")

    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    basecamp = _project_basecamp_or_501(project)

    account_id = str(basecamp["account_id"])
    real_project_id = str(basecamp["project_id"])
    auth_profile = _get_basecamp_auth_profile(storage, account_id)

    applied: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for fix in fixes:
        card_id = fix.get("card_id")
        new_title = fix.get("new_title")
        if not card_id or not new_title:
            failed.append({"card_id": card_id, "error": "card_id y new_title son requeridos"})
            continue
        try:
            await update_card(auth_profile, account_id, real_project_id, str(card_id), title=new_title)
            applied.append({"card_id": card_id, "new_title": new_title})
        except BasecampError as error:
            failed.append({"card_id": card_id, "error": str(error)})

    return {"applied": applied, "failed": failed}


def _parse_bulk_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Formato intermedio genérico compartido por AMBOS parsers de bulk
    create (§7.4): [{list_id/column, title, content, due_on}]. Usado tanto
    por el CSV genérico como por el parser de milestones-v2.md — ambos
    producen esta misma forma para no duplicar la lógica de creación."""
    parsed = []
    for row in rows:
        title = row.get("title")
        if not title:
            continue
        parsed.append(
            {
                "list_id": str(row.get("list_id") or row.get("column") or ""),
                "title": title,
                "content": row.get("content"),
                "due_on": row.get("due_on") or row.get("date"),
            }
        )
    return parsed


@router.post("/projects/{project_id}/basecamp-cards/bulk/preview")
async def preview_basecamp_bulk_cards(
    project_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """§5.4 — preview antes de crear, nunca se crea directo. Acepta `rows`
    ya en el formato intermedio genérico (columna/list_id, title, content,
    due_on) — la fuente (CSV pegado, o el parser de milestones-v2.md,
    ambos en el frontend/§7.4) ya convirtió a esta forma antes de llamar acá."""
    rows = body.get("rows")
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="rows (lista) es requerido")
    return {"preview": _parse_bulk_rows(rows)}


@router.post("/projects/{project_id}/basecamp-cards/bulk")
async def bulk_create_basecamp_cards(
    project_id: str,
    body: dict[str, Any] = Body(...),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """§5.4/§7.4 — crea N cards desde una lista estructurada ya en el
    formato intermedio genérico. Reusa create_card por-fila; una fila que
    falla no aborta el resto (mismo patrón de error explícito por-ítem que
    /apply)."""
    rows = body.get("rows")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=400, detail="rows (lista no vacía) es requerido")

    storage = get_storage()
    projects = storage.read_projects()
    project = _get_owned_project(projects, project_id, current_user)
    basecamp = _project_basecamp_or_501(project)

    account_id = str(basecamp["account_id"])
    real_project_id = str(basecamp["project_id"])
    auth_profile = _get_basecamp_auth_profile(storage, account_id)

    created: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for row in _parse_bulk_rows(rows):
        if not row["list_id"]:
            failed.append({"title": row["title"], "error": "list_id/column vacío"})
            continue
        try:
            result = await create_card(
                auth_profile,
                account_id,
                real_project_id,
                row["list_id"],
                row["title"],
                content_html=row.get("content"),
                due_on=row.get("due_on"),
            )
            created.append(result)
        except BasecampError as error:
            failed.append({"title": row["title"], "error": str(error)})

    return {"created": created, "failed": failed}


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
