"""
Project Brain scheduled sync — HU-003-JarvisMode.

Two triggers call into the same `sync_now(project_id)`:
1. Chat session start — see the "HOOK" comment below for where another agent
   should wire this in (app/routers/jarvis_chat.py or
   app/services/jarvis_chat/session_manager.py). This module intentionally
   does NOT import or edit anything under jarvis_chat/ to avoid stepping on
   that parallel work.
2. The APScheduler cron below, registered on FastAPI startup in app/main.py:
   every 3 hours, 7am-7pm only (hour="7-19/3" — CronTrigger's step syntax:
   fires at 7, 10, 13, 16, 19; never at night).

Design decisions (documented here since the spec leaves them as
implementation calibration):

- "last sync" watermark: uses `Repository.lastSyncAt` (SPEC_JARVIS.md §6.1 /
  app/schemas/project.py) when present. A repo that has never synced before
  (lastSyncAt is None) falls back to a 24h window, per the task instructions
  — this also naturally covers the very first sync right after a repo is
  connected. `lastSyncAt` is updated to "now" after every run that completes
  without error, whether or not it found activity, so the window always
  advances (a quiet 3h slice at 2am-adjacent boundaries doesn't get re-read
  forever).
- No dedicated "sync run" metrics series existed in
  app/schemas/metrics.py / app/services/metrics/collector.py, so this module
  writes its own generic series ("metrics-brain-sync-runs") via
  `storage.append_series` directly — the same generic-by-name mechanism
  collector.py already documents as the reason it doesn't need a change per
  new series. This keeps "the run occurred" observable for analytics even
  when there was no repo activity to ingest, without repurposing
  UsageEvent/OutputCount, which model something else (chat/agent usage,
  per-type output counts).
- Repository auth: `Repository.accessTokenRef` (not an Auth Profile id) is
  what's actually stored on a connected repo (see
  app/routers/repositories.py's connect_repository). Adapters expect an
  `AuthProfile` (RepoAdapter Protocol), so a minimal, synthetic AuthProfile is
  built inline from the repo's own fields (token_ref=accessTokenRef) rather
  than looking up a stored profile by id — there is no auth_profile_id kept
  on Repository to look up.
- Digest ingestion: app/services/brain/ingest.py's real contents are
  `list_recent_events` / `record_event` over project.memory.timeline (a
  generic timeline logger), not a repo-specific "digest" ingester — no such
  function exists yet anywhere in services/brain. `record_event` is reused
  here as-is: one call per repo per run, only when commits or PRs were
  found, formatted as a human-readable summary line. This satisfies "sin
  actividad -> no genera entrada nueva en el Brain" (no record_event call)
  while still registering the run for metrics (see above).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.storage import get_storage
from app.schemas.auth_profile import AuthProfile
from app.schemas.project import Repository
from app.services.brain.ingest import record_event
from app.services.repositories import get_adapter

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW_HOURS = 24
_SYNC_RUNS_SERIES = "metrics-brain-sync-runs"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _parse_since(repo: Repository) -> datetime:
    if repo.lastSyncAt:
        try:
            return datetime.fromisoformat(repo.lastSyncAt.replace("Z", "+00:00"))
        except ValueError:
            pass
    # Never synced before (or an unparseable timestamp) -> 24h default window.
    return _now() - timedelta(hours=_DEFAULT_WINDOW_HOURS)


def _auth_profile_for(repo: Repository) -> AuthProfile:
    """Builds a minimal AuthProfile from the repo's own stored fields.

    Repository only keeps `accessTokenRef` (see app/schemas/project.py /
    app/routers/repositories.py), not an Auth Profile id, so there is nothing
    to look up in app/services/auth_profiles.py here — this synthesizes the
    shape RepoAdapter implementations expect (see github_adapter.py's
    `_resolve_token`, which just reads `token_ref` as an env var name).
    """
    return AuthProfile(
        id=f"sync_{repo.id}",
        provider=repo.provider,
        account=repo.owner,
        token_ref=repo.accessTokenRef,
    )


def _record_sync_run(project_id: str, repo_id: str, environment: str | None, had_activity: bool) -> None:
    storage = get_storage()
    storage.append_series(
        _SYNC_RUNS_SERIES,
        {
            "project_id": project_id,
            "repo_id": repo_id,
            "environment": environment,
            "had_activity": had_activity,
            "ran_at": _now_iso(),
        },
    )


async def _sync_repository(project_id: str, repo: Repository) -> dict[str, Any]:
    """Syncs one connected repo: fetches commits/PRs since its last sync (or
    the 24h default window), ingests a digest if there was activity, and
    always records that the run happened for metrics.

    BUG-009: a per-call failure no longer just gets swallowed into an empty
    list — it's collected in `errors` so the caller can set a real
    `syncStatus`/`lastError` on the Repository instead of silently reporting
    "synced, 0 commits" when the remote API actually failed."""
    adapter = get_adapter(repo.provider)
    auth_profile = _auth_profile_for(repo)
    since = _parse_since(repo)
    errors: list[str] = []

    try:
        commits = await adapter.list_commits_since(auth_profile, repo.owner, repo.repo, since)
    except Exception as error:  # noqa: BLE001 - a flaky remote API must not abort the whole project sync
        logger.exception("sync_scheduler: list_commits_since failed for repo %s", repo.id)
        commits = []
        errors.append(f"commits: {error}")

    try:
        pull_requests = await adapter.list_pull_requests(auth_profile, repo.owner, repo.repo, "all")
    except Exception as error:  # noqa: BLE001
        logger.exception("sync_scheduler: list_pull_requests failed for repo %s", repo.id)
        pull_requests = []
        errors.append(f"pull_requests: {error}")

    had_activity = bool(commits or pull_requests)

    if had_activity:
        record_event(
            project_id,
            agent="sync_scheduler",
            action=(
                f"Brain sync [{repo.environment or 'unknown'}] {repo.owner}/{repo.repo}: "
                f"{len(commits)} commit(s), {len(pull_requests)} PR(s) since {since.isoformat()}"
            ),
        )

    _record_sync_run(project_id, repo.id, repo.environment, had_activity)

    return {
        "repo_id": repo.id,
        "environment": repo.environment,
        "commits": len(commits),
        "pull_requests": len(pull_requests),
        "had_activity": had_activity,
        "errors": errors,
    }


async def sync_one_repository(project_id: str, repo_id: str) -> dict[str, Any]:
    """BUG-009: syncs exactly one repo (used by the connect-time initial
    digest and by the manual "Reintentar" endpoint) and persists its real
    syncStatus/lastError/lastSyncAt on that repo — never a UI-fabricated
    state. Raises HTTPException-free lookup errors as plain exceptions;
    callers (routers) are expected to translate project/repo-not-found into
    404s themselves."""
    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if project is None:
        raise ValueError(f"Unknown project_id: {project_id}")

    repo_dicts = project.get("repositories", [])
    repo_dict = next((r for r in repo_dicts if r.get("id") == repo_id), None)
    if repo_dict is None:
        raise ValueError(f"Unknown repo_id: {repo_id} for project {project_id}")

    repo = Repository(**repo_dict)
    result = await _sync_repository(project_id, repo)

    repo_dict["lastSyncAt"] = _now_iso()
    if result["errors"]:
        repo_dict["syncStatus"] = "error"
        repo_dict["lastError"] = "; ".join(result["errors"])
    else:
        repo_dict["syncStatus"] = "synced"
        repo_dict["lastError"] = None

    storage.write_projects(projects)
    return repo_dict


async def sync_now(project_id: str) -> dict[str, Any]:
    """Syncs the Project Brain for one project: runs `_sync_repository` for
    every connected repo, updates each repo's `lastSyncAt`, and returns a
    summary. Safe to call with a project that has no repositories (returns an
    empty summary) or an unknown project_id (returns {"project_id": ...,
    "repositories": []} without raising, matching the read-only,
    best-effort nature of a background sync trigger).

    HOOK for the chat-session-start trigger (do NOT wire this from here —
    another agent owns jarvis_chat/session_manager.py in parallel):
        from app.cron.sync_scheduler import sync_now
        await sync_now(project_id)
    should be called once, fire-and-forget (or awaited, since it's cheap
    when there are no repos), at the point a new Jarvis Chat session is
    opened for a project.
    """
    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if project is None:
        logger.warning("sync_scheduler.sync_now: unknown project_id %r", project_id)
        return {"project_id": project_id, "repositories": []}

    repo_dicts = project.get("repositories", [])
    if not repo_dicts:
        return {"project_id": project_id, "repositories": []}

    results: list[dict[str, Any]] = []
    for repo_dict in repo_dicts:
        repo = Repository(**repo_dict)
        result = await _sync_repository(project_id, repo)
        repo_dict["lastSyncAt"] = _now_iso()
        # BUG-009: real status, not fabricated — "error" only when a call
        # actually raised, mirrored on the repo so the UI can show it.
        if result["errors"]:
            repo_dict["syncStatus"] = "error"
            repo_dict["lastError"] = "; ".join(result["errors"])
        else:
            repo_dict["syncStatus"] = "synced"
            repo_dict["lastError"] = None
        results.append(result)

    storage.write_projects(projects)

    return {"project_id": project_id, "repositories": results}


async def _sync_all_projects() -> None:
    """Cron job body: iterates every project with at least one connected
    repository and syncs it. Each project is synced independently — one
    project's failure must not block the rest."""
    storage = get_storage()
    projects = storage.read_projects()
    project_ids = [p["id"] for p in projects if p.get("repositories")]

    for project_id in project_ids:
        try:
            await sync_now(project_id)
        except Exception:  # noqa: BLE001 - keep the scheduler loop alive
            logger.exception("sync_scheduler: sync_now failed for project %s", project_id)


_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    """Starts the AsyncIOScheduler with a cron trigger that fires every 3
    hours between 7am and 7pm (hour="7-19/3" -> 7, 10, 13, 16, 19; never at
    night). Idempotent: calling it again returns the already-running
    instance instead of registering a second job (relevant under
    --reload / repeated app startup in dev)."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _sync_all_projects,
        trigger=CronTrigger(hour="7-19/3", minute=0),
        id="brain-sync-daytime",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("sync_scheduler: started (hour='7-19/3')")
    return _scheduler
