"""
TAREA A (Onboarding, 2026-09-11) — standard project folder scaffold.

Folder structure per Mariana's FinanzButik reference (strict order, do not
reinvent): 01-Planning, 02-UX UI, 03-Development, 04-QA, 05-Deliveries,
06-FollowUp. These map best-effort to the 5 existing phase_contracts phases
(planning/backend/frontend/integration_quality/deploy) — "02-UX UI" and
"05-Deliveries"/"06-FollowUp" have NO 1:1 phase today, documented here
instead of inventing new phases to force the fit.
"""

from __future__ import annotations

from typing import Any

from app.schemas.auth_profile import AuthProfile
from app.services.repositories import get_adapter

# (folder, one-line purpose, mapped phase key or None if no 1:1 phase exists)
SCAFFOLD_FOLDERS: list[tuple[str, str, str | None]] = [
    ("01-Planning", "Alcance, milestones, DoD, estimación y timeline del proyecto.", "planning"),
    ("02-UX UI", "Wireframes, diseño visual y prototipos — sin fase equivalente hoy en phase_contracts.", None),
    ("03-Development", "Implementación de backend y frontend.", "backend"),
    ("04-QA", "Gate de calidad, pruebas y recomendación go/no-go.", "integration_quality"),
    ("05-Deliveries", "Entregables y releases al cliente — sin fase equivalente hoy en phase_contracts.", None),
    ("06-FollowUp", "Seguimiento post-entrega — sin fase equivalente hoy en phase_contracts.", None),
]


def _readme_content(folder: str, purpose: str, phase_key: str | None) -> str:
    phase_line = f"\nFase asociada (phase_contracts): `{phase_key}`.\n" if phase_key else (
        "\nSin fase equivalente en phase_contracts hoy — no se fuerza el encaje.\n"
    )
    return f"# {folder}\n\n{purpose}\n{phase_line}"


def _build_auth_profile(repository: dict[str, Any], auth_profiles: list[dict[str, Any]]) -> AuthProfile:
    """Same resolution rule as reconciliation.py's _build_auth_profile:
    accessTokenRef is either an Auth Profile id (looked up in storage) or a
    direct token_ref/env var name."""
    access_token_ref = repository.get("accessTokenRef")
    matched = next((p for p in auth_profiles if p.get("id") == access_token_ref), None)
    if matched is not None:
        return AuthProfile(**matched)
    return AuthProfile(
        id=access_token_ref or "inline",
        provider=repository.get("provider", "github"),
        account=repository.get("owner", ""),
        token_ref=access_token_ref,
    )


# phase_contracts key -> scaffold folder, for TAREA B's "Subir a repo" (a
# ran/activated agent result gets committed into its phase's folder). Phases
# without a 1:1 folder fall back to the closest real folder rather than
# inventing a 7th one.
PHASE_KEY_TO_FOLDER: dict[str, str] = {
    "planning": "01-Planning",
    "backend": "03-Development",
    "frontend": "03-Development",
    "integration_quality": "04-QA",
    "deploy": "06-FollowUp",
}


async def write_phase_artifact(
    repository: dict[str, Any],
    auth_profiles: list[dict[str, Any]],
    phase_key: str,
    filename: str,
    content: str,
) -> str:
    """Commits one activated agent-result artifact into the repo folder
    mapped to `phase_key`. Returns the path written."""
    provider = repository.get("provider")
    owner = repository.get("owner")
    repo = repository.get("repo")
    branch = repository.get("defaultBranch", "main")
    if not (provider and owner and repo):
        raise ValueError("Repository is missing provider/owner/repo")

    folder = PHASE_KEY_TO_FOLDER.get(phase_key, "01-Planning")
    path = f"{folder}/{filename}"

    adapter = get_adapter(provider)
    auth_profile = _build_auth_profile(repository, auth_profiles)
    await adapter.create_or_update_file(
        auth_profile,
        owner,
        repo,
        path,
        content,
        message=f"Add {filename} to {folder}",
        branch=branch,
    )
    return path


async def scaffold_project_repo(
    repository: dict[str, Any], auth_profiles: list[dict[str, Any]]
) -> list[str]:
    """Creates the 6 standard folders (each with a placeholder README.md) in
    the given connected repository. Returns the list of file paths written.
    Raises whatever the adapter raises (e.g. httpx.HTTPStatusError) on
    failure — the caller decides how to surface that."""
    provider = repository.get("provider")
    owner = repository.get("owner")
    repo = repository.get("repo")
    branch = repository.get("defaultBranch", "main")
    if not (provider and owner and repo):
        raise ValueError("Repository is missing provider/owner/repo")

    adapter = get_adapter(provider)
    auth_profile = _build_auth_profile(repository, auth_profiles)

    written: list[str] = []
    for folder, purpose, phase_key in SCAFFOLD_FOLDERS:
        path = f"{folder}/README.md"
        await adapter.create_or_update_file(
            auth_profile,
            owner,
            repo,
            path,
            _readme_content(folder, purpose, phase_key),
            message=f"Add standard project structure: {folder}",
            branch=branch,
        )
        written.append(path)
    return written
