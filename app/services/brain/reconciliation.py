"""
Code<->spec reconciliation — Auditor comparing HU/AC claims of "done" against
real evidence (tests, PRs, commits), per ARCHITECTURE_JARVIS.md §5 and
SPEC_JARVIS.md §6.7/§10 ("nunca reporta 'cumple' sin evidencia; siempre
reporta 'sin test' cuando no hay evidencia").

Real matching per HU-004-JarvisMode: Acceptance Criteria individual vs. test
real que lo verifica.

# CORRECTIONS-PLAN-2026-08-13, P0: Gimena (src/agents/spec-kit-agents/
# Gimena-userstorywriter.md §5, "5. FORMATOS DE SALIDA") never emits "- [ ]"
# checkboxes — that unit never existed in real output, so the reconciler used
# to find zero ACs in every HU and mark it "no_reconciliable" in block. The
# real reconcilable unit, matching Gimena's actual "2. CRITERIOS DE ACEPTACIÓN
# (AC)" structure (see outputs/HU_RUN-001_2026-08-12.md), is:
#   - "2.1 Interfaz y Experiencia" / "2.2 Casos de Uso y Reglas de Negocio":
#     each top-level "- " bullet line (no checkbox) is one AC unit.
#   - "2.3 Manejo de Errores": a markdown table `| Escenario | Mensaje... |`;
#     each data row (excluding the header/separator rows) is one AC unit.
# AC id format: "{huId}-{subsection}.{index}", e.g.
# "HU-004-JarvisMode-2.1.3" (3rd bullet of §2.1) or
# "HU-004-JarvisMode-2.3.1" (1st error-table row of §2.3). Test files link to
# an AC with a comment matching this exact id: "# @ac:HU-004-JarvisMode-2.1.3"
# / "// @ac:HU-004-JarvisMode-2.3.1".

Pipeline:
1. Parse `backlog.md` (HU registry: short id -> full huId + output file) and
   `outputs/*.md` (per-HU Acceptance Criteria: bullets under 2.1/2.2, rows
   under 2.3) from the project's workspace — same file shapes Gimena already
   produces in this repo (see backlog.md / outputs/HU_RUN-001_2026-08-12.md).
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
# JS/TS (`//`) comment style: "# @ac:HU-004-JarvisMode-2.1.3" / "// @ac:...".
# The id after "@ac:" must match the "{huId}-{subsection}.{index}" format
# produced by `_parse_acceptance_criteria` below — see module docstring.
_AC_LINK_RE = re.compile(r"(?:#|//)\s*@ac:([A-Za-z0-9_.\-]+)")

# Matches Gimena's subsection headings within "2. CRITERIOS DE ACEPTACIÓN",
# e.g. "### 2.1. Interfaz y Experiencia (Happy Path)" or
# "### 2.2 Casos de Uso y Reglas de Negocio" or "### 2.3. Manejo de Errores".
# Group 1 is the subsection number ("1", "2", or "3").
_AC_SUBSECTION_RE = re.compile(r"^###\s*2\.(\d+)\.?\s+\S.*$", re.MULTILINE)

# One AC unit per top-level bullet line under 2.1/2.2, e.g.
# "1. Some criterion text." or "- Some criterion text." — Gimena numbers
# 2.1/2.2 items with "1." / "2." / ... or "-", never a checkbox.
_AC_BULLET_RE = re.compile(r"^\s*(?:\d+\.|-)\s+(.+)$", re.MULTILINE)

# One AC unit per data row of the 2.3 "Manejo de Errores" markdown table,
# e.g. "| Escenario X | Mensaje Y |". Skips header/separator rows (the
# separator row is all "-"/":"/"|" characters, filtered in code below).
_AC_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$", re.MULTILINE)

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


def _extract_bullets(section_text: str) -> list[str]:
    """Extracts top-level bullet items ("1. text" / "- text") from a 2.1/2.2
    subsection body, folding indented continuation lines (Gimena wraps long
    bullets across multiple lines) into the same item."""
    top_level_re = re.compile(r"^(?:\d+\.|-)\s+(.*)$")
    bullets: list[str] = []
    current: list[str] = []

    for line in section_text.split("\n"):
        top_match = top_level_re.match(line)
        if top_match:
            if current:
                bullets.append(" ".join(current).strip())
            current = [top_match.group(1).strip()]
        elif line.strip() and line[:1].isspace() and current:
            current.append(line.strip())
        elif not line.strip():
            continue
        else:
            if current:
                bullets.append(" ".join(current).strip())
                current = []

    if current:
        bullets.append(" ".join(current).strip())
    return bullets


def _extract_table_rows(section_text: str) -> list[str]:
    """Extracts data rows from the 2.3 "Manejo de Errores" markdown table
    (`| Escenario | Mensaje... |`), skipping the header row and the
    `| :--- | :--- |` separator row."""
    rows: list[str] = []
    header_seen = False

    for line in section_text.split("\n"):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r"[-: ]*", cell) for cell in cells):
            continue  # separator row, e.g. "| :--- | :--- |"
        if not header_seen:
            header_seen = True
            continue  # header row, e.g. "| Escenario | Mensaje... |"
        rows.append(" | ".join(cells))

    return rows


def _parse_acceptance_criteria(
    workspace: Path, registry: dict[str, dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Parses every HU section across the output files referenced by
    `registry`, returning (ac_units, unreconcilable_hus).

    Real reconcilable unit per Gimena's actual output format (see module
    docstring / Gimena-userstorywriter.md §5): each top-level bullet under
    "2.1 Interfaz y Experiencia" / "2.2 Casos de Uso y Reglas de Negocio", and
    each data row of the "2.3 Manejo de Errores" table. Gimena never emits
    "- [ ]" checkboxes, so that unit is not what this parses.

    ac_units: [{"huId", "acId", "text"}] — acId format
    "{huId}-2.{subsection}.{index}", e.g. "HU-004-JarvisMode-2.1.3".
    unreconcilable_hus: [{"huId", "reason"}] — HUs whose section had no
    parseable AC subsection/bullet/row at all (HU-004-JarvisMode §2.3: "no
    reconciliable").
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

            subsections = list(_AC_SUBSECTION_RE.finditer(section_text))
            hu_ac_count_before = len(ac_units)

            for j, sub_match in enumerate(subsections):
                sub_num = sub_match.group(1)
                sub_start = sub_match.end()
                sub_end = subsections[j + 1].start() if j + 1 < len(subsections) else len(section_text)
                sub_text = section_text[sub_start:sub_end]

                if sub_num == "3":
                    items = _extract_table_rows(sub_text)
                else:
                    items = _extract_bullets(sub_text)

                for idx, item_text in enumerate(items, start=1):
                    ac_units.append(
                        {
                            "huId": hu_id,
                            "acId": f"{hu_id}-2.{sub_num}.{idx}",
                            "text": item_text,
                        }
                    )

            if len(ac_units) == hu_ac_count_before:
                unreconcilable.append(
                    {
                        "huId": hu_id,
                        "reason": "No se encontraron Acceptance Criteria parseables (subsecciones 2.1/2.2/2.3 ausentes o vacías).",
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

    # BUG-010 fix: with 0 connected repos there is no evidence to reconcile
    # against at all (HU-004 §2.3 requires an explicit "no repo connected"
    # response, not fabricated gaps) — short-circuit before parsing any ACs.
    if not project.get("repositories"):
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        reconciliation = {
            "lastRunAt": now,
            "gaps": [],
            "note": "No hay repositorios conectados para este proyecto — no se puede verificar evidencia real.",
        }
        project.setdefault("memory", {}).setdefault("projectBrain", {})["reconciliation"] = reconciliation
        storage.write_projects(projects)
        await record_reconciliation_run(
            project_id=project_id,
            gaps_found=0,
            gaps_closed_since_last=0,
            sin_test=0,
        )
        return reconciliation

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
