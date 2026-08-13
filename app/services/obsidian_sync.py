"""
Exports the app's own memory (Memoria de Mar + per-project Project Brain)
to markdown in a dedicated Obsidian space — SPEC_JARVIS.md §11, resolved
2026-08-14. See scripts/sync_memories_to_obsidian.py's original docstring
for the full rationale; this module holds the actual logic so both the
manual CLI script and app/cron/sync_scheduler.py's periodic job can call
the same code instead of duplicating it.

Snapshot exporter: reads directly from app/core/storage.py (not a running
HTTP round-trip) and fully regenerates the markdown files below on every
call — safe to re-run, not something to hand-edit downstream.

Writes to a fixed local path (the vault lives on Mariana's machine, same
host as the backend in dev and, for now, the only place this runs) rather
than a configurable env var — if this ever needs to run somewhere the vault
isn't mounted, that's the point to make it configurable, not before.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.storage import get_storage

logger = logging.getLogger(__name__)

VAULT_DIR = Path(r"C:\Users\marir\OneDrive\Documentos\Obsidian Vault\Orquestrador 360 - Memoria de la App")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sync_mar_memory(entries: list[dict[str, Any]]) -> int:
    lines = [
        "# Memoria de Mar",
        "",
        f"> Generado por `app/services/obsidian_sync.py` — {_now_iso()}. "
        "No editar a mano, se regenera desde `storage/mar-memory.json`.",
        "",
        f"Total de entradas: {len(entries)}",
        "",
    ]
    if not entries:
        lines.append("_Sin entradas todavía._")
    else:
        by_type: dict[str, list[dict]] = {}
        for entry in entries:
            by_type.setdefault(entry.get("type", "unknown"), []).append(entry)
        for entry_type, group in sorted(by_type.items()):
            lines.append(f"## {entry_type} ({len(group)})")
            lines.append("")
            for entry in sorted(group, key=lambda e: e.get("createdAt", "")):
                lines.append(f"- **{entry.get('createdAt', '?')}** ({entry.get('source', '?')}): {entry.get('content', '')}")
            lines.append("")

    _write(VAULT_DIR / "mar-memory.md", "\n".join(lines))
    return len(entries)


def _project_markdown(project: dict) -> str:
    brain = project.get("memory", {}).get("projectBrain", {})
    decisions = brain.get("decisionLog", [])
    alerts = brain.get("alerts", [])
    meetings = brain.get("meetingLog", [])
    reconciliation = brain.get("reconciliation", {})
    gaps = reconciliation.get("gaps", [])

    lines = [
        f"# {project.get('name', project.get('id'))}",
        "",
        f"> Generado por `app/services/obsidian_sync.py` — {_now_iso()}. "
        "No editar a mano, se regenera desde `storage/projects.json`.",
        "",
        f"- **id**: `{project.get('id')}`",
        f"- **status**: {project.get('status')}",
        f"- **fase actual**: {project.get('currentPhase')} / paso: {project.get('currentStep')}",
        f"- **progreso**: {project.get('progress')}%",
        "",
        f"## Decision Log ({len(decisions)})",
        "",
    ]
    lines += [f"- {d}" for d in decisions] or ["_Sin decisiones registradas._"]

    lines += ["", f"## Alertas ({len(alerts)})", ""]
    lines += [f"- {a}" for a in alerts] or ["_Sin alertas._"]

    lines += ["", f"## Meeting Log ({len(meetings)})", ""]
    lines += [f"- {m}" for m in meetings] or ["_Sin reuniones registradas._"]

    lines += [
        "",
        f"## Reconciliación — Gaps de Acceptance Criteria ({len(gaps)})",
        "",
        f"Última corrida: {reconciliation.get('lastRunAt', 'nunca')}",
        "",
    ]
    if gaps:
        by_status: dict[str, int] = {}
        for gap in gaps:
            by_status[gap.get("status", "unknown")] = by_status.get(gap.get("status", "unknown"), 0) + 1
        lines += [f"- **{status}**: {count}" for status, count in sorted(by_status.items())]
    else:
        lines.append("_Sin gaps registrados (o sin reconciliación corrida todavía)._")

    return "\n".join(lines)


def _sync_projects(projects: list[dict[str, Any]]) -> int:
    index_lines = [
        "# Proyectos — índice",
        "",
        f"> Generado por `app/services/obsidian_sync.py` — {_now_iso()}.",
        "",
    ]
    for project in projects:
        name = project.get("name", project.get("id"))
        slug = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
        _write(VAULT_DIR / "projects" / f"{slug}.md", _project_markdown(project))
        index_lines.append(f"- [[{slug}]] — {project.get('status')}")

    _write(VAULT_DIR / "projects" / "README.md", "\n".join(index_lines))
    return len(projects)


def sync_to_obsidian() -> dict[str, int]:
    """Regenerates the whole "Orquestrador 360 - Memoria de la App" vault
    folder from current storage state. Returns counts for logging/metrics.
    Never raises on an empty/missing store — an empty Mar Memory or project
    list is a valid, real state (see storage.py's read_* defaults), not an
    error condition."""
    storage = get_storage()
    mar_entries = storage.read_mar_memory()
    projects = storage.read_projects()

    _write(
        VAULT_DIR / "README.md",
        "\n".join(
            [
                "# Orquestrador 360 — Memoria de la App",
                "",
                "Espacio dedicado a la memoria PROPIA de la aplicación Orquestrador 360 "
                "(Memoria de Mar + Project Brain por proyecto) — distinto del espacio "
                "`Claude Memory/` (memoria del asistente Claude sobre Mariana y sus "
                "proyectos, no de la app en sí).",
                "",
                "Generado y regenerado por `app/services/obsidian_sync.py`, corrido cada "
                "3h por el mismo cron de `app/cron/sync_scheduler.py` que sincroniza el "
                "Project Brain — no editar estos archivos a mano, se sobreescriben en "
                "cada corrida.",
                "",
                "- [mar-memory.md](mar-memory.md) — entendimiento acumulado del sistema",
                "- [projects/](projects/README.md) — memoria por proyecto (decisiones, "
                "alertas, reuniones, gaps de reconciliación)",
            ]
        ),
    )

    mar_count = _sync_mar_memory(mar_entries)
    project_count = _sync_projects(projects)
    logger.info(
        "obsidian_sync: synced %d Mar Memory entries, %d projects -> %s",
        mar_count,
        project_count,
        VAULT_DIR,
    )
    return {"mar_memory_entries": mar_count, "projects": project_count}
