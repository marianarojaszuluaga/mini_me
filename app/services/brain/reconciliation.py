"""
Code<->spec reconciliation — Auditor comparing HU/AC claims of "done" against
real evidence (tests, PRs, commits), per ARCHITECTURE_JARVIS.md §5 and
SPEC_JARVIS.md §6.7/§10 ("nunca reporta 'cumple' sin evidencia; siempre
reporta 'sin test' cuando no hay evidencia").

Real matching per HU-004-JarvisMode: Acceptance Criteria individual vs. test
real que lo verifica.

Pipeline:
1. Parse `backlog.md` (HU registry: short id -> full huId + output file) and
   `outputs/*.md` (per-HU Acceptance Criteria, one unit per "- [ ]" checkbox)
   from the project's workspace — same file shapes Gimena already produces in
   this repo (see backlog.md / outputs/HU_RUN-001_2026-08-12.md).
2. For each connected repo (`project.repositories[]`), walk the file tree via
   RepoAdapter.get_file_tree, read every file under a "test"-ish path via
   get_file_content, and look for a `@ac:<acId>` link comment (Python `#` or
   JS/TS `//` style).
3. Fold every AC into a `gaps[]`-shaped record: `sin_test` (no linked test),
   `con_test_sin_resultado` (linked test found, but no CI result available
   yet — see TODO below), or `no_reconciliable` (HU has no parseable AC
   checkboxes at all, HU-004 §2.3).

# TODO: calibrar en implementacion — CI result lookup. HU-004-JarvisMode asks
# for "cumple"/"no_cumple" once a linked test's real CI outcome is known, but
# no CI provider API (GitHub Actions / Bitbucket Pipelines) is wired yet in
# this codebase. Rather than invent a result, a linked test is left in the
# honest intermediate state "con_test_sin_resultado" until that integration
# lands — never a fabricated "cumple".
#
# TODO: calibrar en implementacion — workspace path. Gimena's backlog.md /
# outputs/*.md live at the repo root today (single-project setup). Once
# multi-project workspaces exist, `project["workspacePath"]` (if/when that
# field is added to the Project schema) should override `REPO_ROOT` below.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT
from app.core.storage import get_storage
from app.schemas.auth_profile import AuthProfile
from app.services.metrics.collector import record_reconciliation_run
from app.services.repositories import get_adapter

# Convention chosen for linking a test to the AC it verifies: a comment
# anywhere in a file whose path contains "test", in either Python (`#`) or
# JS/TS (`//`) comment style: "# @ac:HU-004-JarvisMode-2" / "// @ac:...".
_AC_LINK_RE = re.compile(r"(?:#|//)\s*@ac:([A-Za-z0-9_.\-]+)")

# One Acceptance Criterion unit per unchecked/checked markdown checkbox line,
# e.g. "- [ ] Some criterion text." / "- [x] Some criterion text.".
_AC_CHECKBOX_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s+(.+)$", re.MULTILINE)

# Matches Gimena's per-HU section headings, e.g. "# [HU-004]: ...".
_HU_SECTION_RE = re.compile(r"^#\s*\[(HU-\d+)\][^\n]*$", re.MULTILINE)

# Matches backlog.md's "Registro Maestro" table rows:
# "| HU-004-JarvisMode | Title | Output File |".
_BACKLOG_ROW_RE = re.compile(
    r"^\|\s*(HU-\d+-[A-Za-z0-9]+)\s*\|[^|]*\|\s*([^\s|][^|]*?\.md)\s*\|\s*$",
    re.MULTILINE,
)


def _workspace_root(project: dict[str, Any]) -> Path:
    workspace_path = project.get("workspacePath")
    return Path(workspace_path) if workspace_path else REPO_ROOT


def _parse_backlog_registry(workspace: Path) -> dict[str, dict[str, str]]:
    """Reads backlog.md's master registry, mapping the HU short id (e.g.
    "HU-004") to {"huId": "HU-004-JarvisMode", "outputFile": "outputs/..."}."""
    backlog_path = workspace / "backlog.md"
    if not backlog_path.is_file():
        return {}

    text = backlog_path.read_text(encoding="utf-8", errors="replace")
    registry: dict[str, dict[str, str]] = {}
    for full_hu_id, output_file in _BACKLOG_ROW_RE.findall(text):
        short_id = full_hu_id.split("-")[0] + "-" + full_hu_id.split("-")[1]
        registry[short_id] = {
            "huId": full_hu_id,
            "outputFile": output_file.strip(),
        }
    return registry


def _parse_acceptance_criteria(
    workspace: Path, registry: dict[str, dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Parses every HU section across the output files referenced by
    `registry`, returning (ac_units, unreconcilable_hus).

    ac_units: [{"huId", "acId", "text"}] — one per "- [ ]" checkbox found
    inside that HU's section.
    unreconcilable_hus: [{"huId", "reason"}] — HUs whose section had no
    parseable checkbox at all (HU-004-JarvisMode §2.3: "no reconciliable").
    """
    ac_units: list[dict[str, str]] = []
    unreconcilable: list[dict[str, str]] = []

    output_files = {info["outputFile"] for info in registry.values()}
    short_to_full = {short: info["huId"] for short, info in registry.items()}

    for output_file in output_files:
        output_path = workspace / output_file
        if not output_path.is_file():
            output_path = workspace / "outputs" / Path(output_file).name
        if not output_path.is_file():
            continue

        text = output_path.read_text(encoding="utf-8", errors="replace")
        headings = list(_HU_SECTION_RE.finditer(text))
        for i, match in enumerate(headings):
            short_id = match.group(1)
            hu_id = short_to_full.get(short_id, short_id)
            section_start = match.end()
            section_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            section_text = text[section_start:section_end]

            checkboxes = _AC_CHECKBOX_RE.findall(section_text)
            if not checkboxes:
                unreconcilable.append(
                    {"huId": hu_id, "reason": "No se encontraron Acceptance Criteria en formato checkbox."}
                )
                continue

            for idx, (_checked, criterion_text) in enumerate(checkboxes, start=1):
                ac_units.append(
                    {
                        "huId": hu_id,
                        "acId": f"{hu_id}-{idx}",
                        "text": criterion_text.strip(),
                    }
                )

    return ac_units, unreconcilable


def _build_auth_profile(repository: dict[str, Any], auth_profiles: list[dict[str, Any]]) -> AuthProfile:
    """Resolves the AuthProfile for a connected repository.

    `Repository.accessTokenRef` (ARCHITECTURE_JARVIS.md §9.3 / schemas/project.py)
    is documented as either an Auth Profile id or a direct env var reference.
    We try the former first (look it up in storage's auth-profiles.json) and
    fall back to treating the value itself as `token_ref`, matching how
    GitHubAdapter/BitbucketAdapter._resolve_token already reads it.
    """
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


async def _collect_test_links(project: dict[str, Any]) -> dict[str, str]:
    """Walks every connected repo's file tree, reads files under a "test"-ish
    path, and returns {acId: "owner/repo:path"} for every `@ac:<acId>` link
    comment found. Best-effort: a repo/file that fails to read is skipped
    rather than failing the whole reconciliation run."""
    repositories = project.get("repositories", [])
    if not repositories:
        return {}

    auth_profiles = get_storage().read_auth_profiles()
    links: dict[str, str] = {}

    for repository in repositories:
        provider = repository.get("provider")
        owner = repository.get("owner")
        repo = repository.get("repo")
        branch = repository.get("defaultBranch", "main")
        if not (provider and owner and repo):
            continue

        try:
            adapter = get_adapter(provider)
            auth_profile = _build_auth_profile(repository, auth_profiles)
            file_tree = await adapter.get_file_tree(auth_profile, owner, repo, branch)
        except Exception:
            # Repo unreachable this run (token revoked, rate limit, etc.) —
            # its ACs simply stay "sin_test", not a hard failure.
            continue

        test_paths = [node.path for node in file_tree if node.type == "file" and "test" in node.path.lower()]

        for path in test_paths:
            try:
                content = await adapter.get_file_content(auth_profile, owner, repo, path, branch)
            except Exception:
                continue

            for ac_id in _AC_LINK_RE.findall(content):
                links.setdefault(ac_id, f"{owner}/{repo}:{path}")

    return links


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

    workspace = _workspace_root(project)
    registry = _parse_backlog_registry(workspace)
    ac_units, unreconcilable_hus = _parse_acceptance_criteria(workspace, registry)
    test_links = await _collect_test_links(project)

    gaps: list[dict[str, Any]] = []
    sin_test = 0

    for ac in ac_units:
        test_ref = test_links.get(ac["acId"])
        if test_ref is None:
            status = "sin_test"
            sin_test += 1
        else:
            # No CI provider wired yet (see module TODO) — a linked test is
            # real evidence of *intent to verify*, not yet a pass/fail result.
            status = "con_test_sin_resultado"

        gaps.append(
            {
                "huId": ac["huId"],
                "acceptanceCriterion": ac["text"],
                "claim": "done",
                "testRef": test_ref,
                "evidence": test_ref,
                "status": status,
            }
        )

    for unreconcilable in unreconcilable_hus:
        gaps.append(
            {
                "huId": unreconcilable["huId"],
                "acceptanceCriterion": None,
                "claim": "done",
                "testRef": None,
                "evidence": None,
                "status": "no_reconciliable",
                "reason": unreconcilable["reason"],
            }
        )

    def _is_open(gap: dict[str, Any]) -> bool:
        return gap.get("status") in ("sin_test", "no_reconciliable")

    # `status: "open"` is kept alongside the finer-grained status above so
    # existing consumers that filter on gaps[].status == "open" (pre-HU-004
    # behavior) keep working without a breaking schema change.
    for gap in gaps:
        if _is_open(gap):
            gap.setdefault("legacyStatus", "open")

    previous = project.get("memory", {}).get("projectBrain", {}).get("reconciliation") or {}
    previous_open_ids = {
        g.get("huId") for g in previous.get("gaps", []) if g.get("status") == "open" or _is_open(g)
    }
    current_open_ids = {g["huId"] for g in gaps if _is_open(g)}
    gaps_closed_since_last = len(previous_open_ids - current_open_ids)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    reconciliation: dict[str, Any] = {"lastRunAt": now, "gaps": gaps}
    if not project.get("repositories"):
        reconciliation["note"] = "No hay repositorios conectados para este proyecto — no se puede verificar evidencia real."

    project.setdefault("memory", {}).setdefault("projectBrain", {})["reconciliation"] = reconciliation
    storage.write_projects(projects)

    await record_reconciliation_run(
        project_id=project_id,
        gaps_found=len(gaps),
        gaps_closed_since_last=gaps_closed_since_last,
        sin_test=sin_test,
    )

    return reconciliation
