"""
Pydantic models for Project + Project Brain.

Shape matches storage/projects.json exactly (the real JSON already on disk in
this repo), extended with `repositories: list[Repository]` per
SPEC_JARVIS.md §6.1 (the CRUD for repositories is implemented by another
agent later — the schema exists now so other modules can import it).

All fields default so a bare `Project(...)` with just the required identity
fields still produces the same default shape as newProjectRecord() /
defaultProjectBrain() in server.js.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Project Brain
# ---------------------------------------------------------------------------


class DecisionLogEntry(BaseModel):
    decision: str
    context: str | None = None
    timestamp: str | None = None
    source: str | None = None
    # Allow extra fields: Gabriela's extraction prompt is free-form JSON per
    # acta and other keys may show up (see agent_registry.build_acta_ingest_prompt).
    model_config = {"extra": "allow"}


class AlertEntry(BaseModel):
    alert: str
    severity: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    timestamp: str | None = None
    status: Literal["open", "closed"] | None = "open"
    source: str | None = None
    model_config = {"extra": "allow"}


class MeetingLogEntry(BaseModel):
    timestamp: str | None = None
    meetingTitle: str | None = None
    docLink: str | None = None
    date: str | None = None
    model_config = {"extra": "allow"}


class ReconciliationGap(BaseModel):
    huId: str | None = None
    claim: str | None = None
    evidence: str | None = None
    status: Literal["open", "closed"] = "open"
    model_config = {"extra": "allow"}


class Reconciliation(BaseModel):
    """New in SPEC_JARVIS.md §6.1 — result of the last reconciliation run
    (Auditor comparing HU claims of "done" against actual evidence)."""

    lastRunAt: str | None = None
    gaps: list[ReconciliationGap] = Field(default_factory=list)


class ProjectBrain(BaseModel):
    status: Literal["pending", "active"] = "pending"
    decisionLog: list[DecisionLogEntry] = Field(default_factory=list)
    alerts: list[AlertEntry] = Field(default_factory=list)
    meetingLog: list[MeetingLogEntry] = Field(default_factory=list)
    reconciliation: Reconciliation | None = None


# ---------------------------------------------------------------------------
# Backlogs / sprints / timeline (project.memory.*)
# ---------------------------------------------------------------------------


class HuBacklog(BaseModel):
    status: Literal["pending", "active", "done"] = "pending"
    ids: list[str] = Field(default_factory=list)


class PlansBacklog(BaseModel):
    status: Literal["pending", "active", "done"] = "pending"
    plans: list[Any] = Field(default_factory=list)


class ActasBacklog(BaseModel):
    status: Literal["pending", "active", "done"] = "pending"
    actas: list[Any] = Field(default_factory=list)


class Backlogs(BaseModel):
    hu: HuBacklog = Field(default_factory=HuBacklog)
    plans: PlansBacklog = Field(default_factory=PlansBacklog)
    actas: ActasBacklog = Field(default_factory=ActasBacklog)


class Sprints(BaseModel):
    current: int = 1
    status: Literal["pending", "active", "done"] = "pending"


class TimelineActivity(BaseModel):
    timestamp: str
    agent: str | None = None
    action: str
    status: str = "completed"
    model_config = {"extra": "allow"}


class Timeline(BaseModel):
    createdAt: str = Field(default_factory=_now_iso)
    activities: list[TimelineActivity] = Field(default_factory=list)


class BasecampCardTableCard(BaseModel):
    title: str
    dueOn: str | None = None
    assignees: list[str] = Field(default_factory=list)


class BasecampCardTableColumn(BaseModel):
    name: str
    cards: list[BasecampCardTableCard] = Field(default_factory=list)


class BasecampMirror(BaseModel):
    """Real snapshot of the linked Basecamp project — Tarea 2 Gap 3: name/
    description/status plus the selected Card Tables' real columns+cards.
    Refreshed on every Dashboard load; never fabricated if Basecamp doesn't
    respond (the router surfaces an explicit error instead)."""

    name: str | None = None
    description: str | None = None
    cardTables: list[dict[str, Any]] = Field(default_factory=list)
    lastSyncAt: str | None = None


class ProjectMemory(BaseModel):
    projectBrain: ProjectBrain = Field(default_factory=ProjectBrain)
    backlogs: Backlogs = Field(default_factory=Backlogs)
    sprints: Sprints = Field(default_factory=Sprints)
    timeline: Timeline = Field(default_factory=Timeline)
    # Tarea 2 Gap 3 — real Basecamp mirror, separate from projectBrain/
    # backlogs (doesn't overwrite either), None until first synced.
    basecampMirror: BasecampMirror | None = None
    # Tarea 3 — persisted QaSweepReport history (app/schemas/qa.py), kept as
    # plain dicts here to avoid a schema-module cycle; the real shape is
    # enforced where it's written (app/routers/agents.py).
    qaSweeps: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Repository (SPEC_JARVIS.md §6.1 — new, CRUD implemented by another agent)
# ---------------------------------------------------------------------------


class Repository(BaseModel):
    id: str
    provider: Literal["github", "bitbucket"]
    owner: str
    repo: str
    defaultBranch: str = "main"
    # Real multi-branch monitoring, added 2026-08-14 (Mariana: "debería poder
    # agregar... varias ramas del Repo"). defaultBranch stays for back-compat
    # with data written before this field existed; branches is the real list
    # a UI should read/write. NOTE: the sync adapters don't yet filter
    # commits/PRs per-branch (list_commits_since has no branch param) — this
    # stores the intent for real, but the cron sync still reads repo-wide
    # activity until the adapters gain branch scoping.
    branches: list[str] = Field(default_factory=lambda: ["main"])
    # "prod" vs "develop" — see ARCHITECTURE_JARVIS.md §9.3.
    environment: Literal["prod", "develop"] | None = None
    connectedAt: str = Field(default_factory=_now_iso)
    lastSyncAt: str | None = None
    # Never the token in clear text — a reference to where it's actually
    # stored (e.g. "env:GITHUB_TOKEN_PROJ_X" or an Auth Profile id).
    accessTokenRef: str | None = None
    # BUG-009 (qa/CORRECTIONS-PLAN-2026-08-13.md P2): real sync state, driven
    # by app/cron/sync_scheduler.py — "never" until the first sync attempt
    # runs (connect, retry, or the cron), never a UI-fabricated state.
    syncStatus: Literal["never", "synced", "error"] = "never"
    lastError: str | None = None


# ---------------------------------------------------------------------------
# Basecamp link (2026-08-14) — a project can point at a real Basecamp
# project (account_id + project_id), used for "Ver en Basecamp" and, once a
# real adapter reads sprint/to-do data, the Dashboard's "Estadísticas del
# proyecto" section. Separate from Repository — a Basecamp project isn't a
# code repo, it's a project-management link.
# ---------------------------------------------------------------------------


class BasecampPublishConfig(BaseModel):
    """Basecamp Message Board Publisher (2026-09-07) — config por proyecto,
    adaptado de SPEC-basecamp-message-board-publisher.md §1.9. Default
    `enabled=False`: ningún proyecto empieza a publicar sin activación
    explícita (HU-043 CA-1)."""

    enabled: bool = False
    publish_on_start: bool = True
    publish_on_close: bool = True
    category_id: int | None = None
    notify_person_ids: list[int] = Field(default_factory=list)


class BasecampLink(BaseModel):
    account_id: str
    project_id: str
    # Tarea 2 Gap 3 (2026-08-21, corrección de Mariana): la fuente real de
    # "sprint actual" son las Card Tables (Kanban), nunca el todolist — un
    # proyecto puede tener más de una, así que se guarda cuáles quedaron
    # elegidas como fuente en vez de asumir "la primera que aparezca".
    selectedCardTableIds: list[str] = Field(default_factory=list)
    # Cacheado desde el `dock` del proyecto real de Basecamp — evita pegarle
    # a GET /projects/{id}.json en cada publicación (SPEC §1.3, §1.7).
    message_board_id: str | None = None
    publish: BasecampPublishConfig = Field(default_factory=BasecampPublishConfig)


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class Project(BaseModel):
    id: str
    name: str
    owner: str | None = None
    description: str | None = None
    currentPhase: int = 1
    currentStep: str = "iniciando"
    status: Literal["active", "paused", "done", "archived"] = "active"
    progress: int = 0
    createdAt: str = Field(default_factory=_now_iso)
    memory: ProjectMemory = Field(default_factory=ProjectMemory)
    # New in SPEC_JARVIS.md §6.1. A Project can have 0, 1, or N repos.
    repositories: list[Repository] = Field(default_factory=list)
    basecamp: BasecampLink | None = None


class ProjectCreateRequest(BaseModel):
    name: str
    owner: str | None = None
    description: str | None = None
    phase: int | None = None
