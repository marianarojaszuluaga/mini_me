"""
Repository connections + Auth Profiles — SPEC_JARVIS.md §6.1/§6.2,
ARCHITECTURE_JARVIS.md §1.

# TODO: calibrar en implementacion — the parallel "repositories" phase left
# only services/repositories/base.py + __init__.py (the adapter Protocol and
# registry) on disk, no router. This is the integration agent's fill-in: CRUD
# for repositories nested under a project, plus the Auth Profile endpoints
# that auth_profiles.py's service already implemented but nothing exposed.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.security import authenticate_token
from app.core.storage import get_storage
from app.schemas.auth_profile import AuthProfile, AuthProfileCreateRequest
from app.schemas.project import Repository
from app.services import auth_profiles
from app.services.repositories import get_adapter

router = APIRouter(dependencies=[Depends(authenticate_token)])


def _new_repo_id(provider: str, repo: str) -> str:
    return f"{provider}_{repo}_{int(time.time() * 1000)}"


def _find_project(projects: list[dict[str, Any]], project_id: str) -> dict[str, Any]:
    project = next((p for p in projects if p.get("id") == project_id), None)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# -- Auth Profiles ------------------------------------------------------------


@router.get("/auth-profiles")
async def list_auth_profiles() -> list[AuthProfile]:
    return auth_profiles.list_auth_profiles()


@router.post("/auth-profiles", status_code=201)
async def create_auth_profile(body: AuthProfileCreateRequest) -> AuthProfile:
    return auth_profiles.create_auth_profile(body)


@router.delete("/auth-profiles/{profile_id}")
async def delete_auth_profile(profile_id: str) -> dict[str, Any]:
    deleted = auth_profiles.delete_auth_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Auth profile not found")
    return {"deleted": True, "id": profile_id}


# -- Repositories (nested under a project) -----------------------------------


@router.get("/projects/{project_id}/repositories")
async def list_repositories(project_id: str) -> list[dict[str, Any]]:
    storage = get_storage()
    project = _find_project(storage.read_projects(), project_id)
    return project.get("repositories", [])


@router.post("/projects/{project_id}/repositories", status_code=201)
async def connect_repository(
    project_id: str,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Connects a repo to a project. Validates access via the appropriate
    adapter before persisting, using the Auth Profile named by
    `auth_profile_id` (its provider must match `provider`)."""
    provider = body.get("provider")
    owner = body.get("owner")
    repo_name = body.get("repo")
    auth_profile_id = body.get("auth_profile_id")
    environment = body.get("environment")
    default_branch = body.get("defaultBranch", "main")

    if not provider or not owner or not repo_name:
        raise HTTPException(status_code=400, detail="provider, owner and repo are required")
    if not environment:
        raise HTTPException(status_code=400, detail="environment is required")

    storage = get_storage()
    projects = storage.read_projects()
    project = _find_project(projects, project_id)

    for existing in project.get("repositories", []):
        if (
            existing.get("provider") == provider
            and existing.get("owner") == owner
            and existing.get("repo") == repo_name
            and existing.get("environment") == environment
        ):
            raise HTTPException(
                status_code=409,
                detail="Repository already connected to this project with this environment",
            )

    auth_profile = auth_profiles.get_auth_profile(auth_profile_id) if auth_profile_id else None
    if auth_profile_id and auth_profile is None:
        raise HTTPException(status_code=404, detail="Auth profile not found")
    if auth_profile is not None and auth_profile.provider != provider:
        raise HTTPException(
            status_code=400, detail="Auth profile provider does not match repository provider"
        )

    try:
        adapter = get_adapter(provider)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if auth_profile is not None:
        has_access = await adapter.validate_access(auth_profile, owner, repo_name)
        if not has_access:
            raise HTTPException(status_code=403, detail="Could not validate access to repository")

    new_repo = Repository(
        id=_new_repo_id(provider, repo_name),
        provider=provider,
        owner=owner,
        repo=repo_name,
        defaultBranch=default_branch,
        environment=environment,
        accessTokenRef=auth_profile.token_ref if auth_profile else None,
    )

    project.setdefault("repositories", []).append(new_repo.model_dump())
    storage.write_projects(projects)

    return new_repo.model_dump()


@router.delete("/projects/{project_id}/repositories/{repo_id}")
async def disconnect_repository(project_id: str, repo_id: str) -> dict[str, Any]:
    storage = get_storage()
    projects = storage.read_projects()
    project = _find_project(projects, project_id)

    repos = project.get("repositories", [])
    remaining = [r for r in repos if r.get("id") != repo_id]
    if len(remaining) == len(repos):
        raise HTTPException(status_code=404, detail="Repository not connected to this project")

    project["repositories"] = remaining
    storage.write_projects(projects)
    return {"deleted": True, "id": repo_id}
