"""
Sync the app's own memory (Memoria de Mar + per-project Project Brain data)
into a dedicated Obsidian space — SPEC_JARVIS.md §11, resolved 2026-08-14 in
response to Mariana's "manten todas las memorias guardadas de forma
permanente en Obsidian, en un nuevo espacio" (item 3.1), clarified as
covering BOTH kinds of memory ("ambos") plus per-project memory ("y las de
los proyectos"):

  - Claude's own assistant memory (user/feedback/project/reference) already
    lives in `Obsidian Vault/Claude Memory/` per the global CLAUDE.md
    instruction — that space is untouched by this script.
  - This script covers the OTHER kind: Orquestrador 360's own operational
    memory — Memoria de Mar (storage/mar-memory.json) and each project's
    Project Brain (decisionLog/alerts/meetingLog/reconciliation gaps, inside
    storage/projects.json) — which had nowhere durable outside the app's own
    JSON storage until now.

Reads directly from storage/*.json (no running server needed) and
regenerates markdown files under a new vault folder,
`Obsidian Vault/Orquestrador 360 - Memoria de la App/`. Idempotent/safe to
re-run: each run fully regenerates the files below from current storage
state, so it's a snapshot exporter, not something to hand-edit downstream.

This is NOT wired into a scheduler yet — run manually after real Mar Memory
entries and project brain data accumulate. Wiring it into
app/cron/sync_scheduler.py's periodic job is a reasonable next step once
this snapshot form is confirmed useful, not assumed necessary yet.

Usage:
    python scripts/sync_memories_to_obsidian.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STORAGE_DIR = REPO_ROOT / "storage"
VAULT_DIR = Path(r"C:\Users\marir\OneDrive\Documentos\Obsidian Vault\Orquestrador 360 - Memoria de la App")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(name: str):
    path = STORAGE_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def sync_mar_memory() -> int:
    data = _read_json("mar-memory.json") or {"entries": []}
    entries = data.get("entries", [])

    lines = [
        "# Memoria de Mar",
        "",
        f"> Generado por `scripts/sync_memories_to_obsidian.py` — {_now_iso()}. "
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
        f"> Generado por `scripts/sync_memories_to_obsidian.py` — {_now_iso()}. "
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
    if decisions:
        for d in decisions:
            lines.append(f"- {d}")
    else:
        lines.append("_Sin decisiones registradas._")

    lines += ["", f"## Alertas ({len(alerts)})", ""]
    if alerts:
        for a in alerts:
            lines.append(f"- {a}")
    else:
        lines.append("_Sin alertas._")

    lines += ["", f"## Meeting Log ({len(meetings)})", ""]
    if meetings:
        for m in meetings:
            lines.append(f"- {m}")
    else:
        lines.append("_Sin reuniones registradas._")

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
        for status, count in sorted(by_status.items()):
            lines.append(f"- **{status}**: {count}")
    else:
        lines.append("_Sin gaps registrados (o sin reconciliación corrida todavía)._")

    return "\n".join(lines)


def sync_projects() -> int:
    projects = _read_json("projects.json") or []
    index_lines = [
        "# Proyectos — índice",
        "",
        f"> Generado por `scripts/sync_memories_to_obsidian.py` — {_now_iso()}.",
        "",
    ]
    for project in projects:
        name = project.get("name", project.get("id"))
        slug = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
        _write(VAULT_DIR / "projects" / f"{slug}.md", _project_markdown(project))
        index_lines.append(f"- [[{slug}]] — {project.get('status')}")

    _write(VAULT_DIR / "projects" / "README.md", "\n".join(index_lines))
    return len(projects)


def main() -> None:
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
                "Generado y regenerado por `scripts/sync_memories_to_obsidian.py` en el "
                "repo `orquestrador-360` — no editar estos archivos a mano, se sobreescriben "
                "en cada corrida.",
                "",
                "- [mar-memory.md](mar-memory.md) — entendimiento acumulado del sistema",
                "- [projects/](projects/README.md) — memoria por proyecto (decisiones, "
                "alertas, reuniones, gaps de reconciliación)",
            ]
        ),
    )
    mar_count = sync_mar_memory()
    project_count = sync_projects()
    print(f"Sincronizado: {mar_count} entradas de Mar Memory, {project_count} proyectos -> {VAULT_DIR}")


if __name__ == "__main__":
    main()
