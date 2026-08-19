"""
Storage abstraction: filesystem locally, Redis (Upstash, via Vercel
Marketplace) in serverless. Ported from store.js — same function shapes,
same env-var suffix matching for Vercel's dynamically-prefixed Redis vars.

Local dev / self-hosted: STORAGE_DIR is a real, persistent disk — plain JSON
files work fine, no Redis needed.

Serverless (Vercel): there is no persistent disk across invocations. If Redis
REST credentials are present (directly or via a suffix-matched, prefixed env
var from the Redis Marketplace integration), reads/writes go there instead.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.config import get_settings

_PREFIXED_URL_SUFFIXES = ("_KV_REST_API_URL", "_REDIS_REST_URL")
_PREFIXED_TOKEN_SUFFIXES = ("_KV_REST_API_TOKEN", "_REDIS_REST_TOKEN")


def _find_env_by_suffix(suffixes: tuple[str, ...]) -> str | None:
    for key, value in os.environ.items():
        if any(key.endswith(suffix) for suffix in suffixes):
            return value
    return None


def _resolve_redis_credentials() -> tuple[str | None, str | None]:
    settings = get_settings()
    url = (
        settings.UPSTASH_REDIS_REST_URL
        or os.environ.get("KV_REST_API_URL")
        or _find_env_by_suffix(_PREFIXED_URL_SUFFIXES)
    )
    token = (
        settings.UPSTASH_REDIS_REST_TOKEN
        or os.environ.get("KV_REST_API_TOKEN")
        or _find_env_by_suffix(_PREFIXED_TOKEN_SUFFIXES)
    )
    return url, token


class Storage:
    """Filesystem/Redis-backed store. One instance per process is enough —
    get_storage() below caches it."""

    def __init__(self) -> None:
        settings = get_settings()
        self.storage_dir = Path(settings.STORAGE_DIR)
        redis_url, redis_token = _resolve_redis_credentials()
        self.using_kv = bool(redis_url and redis_token)
        self._redis = None
        self.kv_init_error: str | None = None  # TEMP diagnostic, 2026-08-19

        if self.using_kv:
            # Real bug found 2026-08-14: a stale Vercel Marketplace Redis
            # integration (added, then never actually provisioned with a
            # real database — "nunca la hemos configurado") left
            # *_KV_REST_API_URL/TOKEN env vars in production. This branch
            # had NO error handling at all, so instantiating a client
            # against a non-existent/broken Redis silently took down every
            # route that calls get_storage() (GET /health, /projects, ...)
            # with a raw 500 — including endpoints that don't even read
            # data, since the crash happened in the client constructor
            # itself. Falls back to filesystem mode instead of crashing the
            # whole app over a broken KV credential.
            try:
                # Lazy-imported: local/file-mode deployments never need this
                # package installed.
                from upstash_redis import Redis  # type: ignore[import-not-found]

                self._redis = Redis(url=redis_url, token=redis_token)
            except Exception as error:  # noqa: BLE001 - a broken KV config must degrade, never crash every route
                print(f"storage.py: Redis/KV init failed, falling back to filesystem: {error}")
                self.kv_init_error = f"{type(error).__name__}: {error}"
                self.using_kv = False
                self._redis = None

        if not self.using_kv:
            try:
                self.storage_dir.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                # Fail soft: a crashed module load takes the whole app down.
                # Reads return empty and writes silently no-op below instead.
                print(f"storage.py: could not create STORAGE_DIR ({self.storage_dir}): {error}")

    def _file_path(self, name: str) -> Path:
        return self.storage_dir / f"{name}.json"

    def _read_list(self, name: str) -> list[Any]:
        if self.using_kv and self._redis is not None:
            try:
                value = self._redis.get(name)
                if value is None:
                    return []
                # Real bug found 2026-08-19: upstash_redis's client
                # auto-serializes on .set() (Python list -> JSON string) but
                # does NOT auto-deserialize on .get() — it returns the raw
                # JSON string as-is. Every real read after the Redis path
                # actually started working (once upstash-redis was moved to
                # base deps) crashed downstream code that expected a list
                # (iterating a string iterates characters) with an uncaught
                # 500. Parse explicitly instead of trusting the client.
                if isinstance(value, str):
                    return json.loads(value)
                return value
            except Exception as error:  # noqa: BLE001 - a flaky KV call must not 500 the whole route
                print(f'storage.py: Redis read_list("{name}") failed: {error}')
                return []
        try:
            file_path = self._file_path(name)
            if not file_path.exists():
                return []
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f'storage.py: read_list("{name}") failed: {error}')
            return []

    def _write_list(self, name: str, value: list[Any]) -> None:
        if self.using_kv and self._redis is not None:
            try:
                self._redis.set(name, value)
            except Exception as error:  # noqa: BLE001 - a flaky KV call must not 500 the whole route
                print(f'storage.py: Redis write_list("{name}") failed: {error}')
            return
        try:
            self._file_path(name).write_text(
                json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as error:
            print(f'storage.py: write_list("{name}") failed: {error}')

    def _append_log(self, name: str, entry: dict[str, Any]) -> None:
        logs = self._read_list(name)
        logs.append(entry)
        self._write_list(name, logs)

    # -- public API, same names/shapes as store.js -------------------------

    def read_projects(self) -> list[dict[str, Any]]:
        return self._read_list("projects")

    def write_projects(self, projects: list[dict[str, Any]]) -> None:
        self._write_list("projects", projects)

    def read_workflows(self) -> list[dict[str, Any]]:
        return self._read_list("workflows")

    def write_workflows(self, workflows: list[dict[str, Any]]) -> None:
        self._write_list("workflows", workflows)

    def log_activity(self, entry: dict[str, Any]) -> None:
        self._append_log("activity-log", entry)

    def log_tool_invocation(self, entry: dict[str, Any]) -> None:
        self._append_log("orchestrator-log", entry)

    def read_auth_profiles(self) -> list[dict[str, Any]]:
        return self._read_list("auth-profiles")

    def write_auth_profiles(self, profiles: list[dict[str, Any]]) -> None:
        self._write_list("auth-profiles", profiles)

    # -- generic time-series helpers (metrics layer) ------------------------
    # Not JS-ported: new for app/services/metrics/*. Kept generic (by series
    # name) rather than one method per metric type so collector.py doesn't
    # need a storage.py change every time a new series is added.

    def read_series(self, series: str) -> list[dict[str, Any]]:
        """Reads an append-only time-series log, e.g. 'metrics-agent-evaluations'."""
        return self._read_list(series)

    def append_series(self, series: str, entry: dict[str, Any]) -> None:
        """Appends one record to an append-only time-series log."""
        self._append_log(series, entry)

    def write_series(self, series: str, entries: list[dict[str, Any]]) -> None:
        """Overwrites a whole time-series log (used for counter compaction)."""
        self._write_list(series, entries)

    def read_mar_memory(self) -> list[dict[str, Any]]:
        """Memoria de Mar (SPEC_JARVIS.md §6.3) — system-level, not
        per-project. Stored as storage/mar-memory.json with shape
        {"entries": [...]}, but exposed here as the flat entries list
        (same convention as read_projects/read_workflows)."""
        wrapper = self._read_dict("mar-memory")
        entries = wrapper.get("entries")
        return entries if isinstance(entries, list) else []

    def write_mar_memory(self, entries: list[dict[str, Any]]) -> None:
        self._write_dict("mar-memory", {"entries": entries})

    def read_chat_sessions(self) -> list[dict[str, Any]]:
        """Jarvis Chat sessions (ARCHITECTURE_JARVIS.md §2.3 / SPEC_JARVIS.md
        §6.6) — storage/jarvis-sessions.json, shape {"sessions": [...]}.
        Exposed flat (same convention as read_mar_memory)."""
        wrapper = self._read_dict("jarvis-sessions")
        sessions = wrapper.get("sessions")
        return sessions if isinstance(sessions, list) else []

    def write_chat_sessions(self, sessions: list[dict[str, Any]]) -> None:
        self._write_dict("jarvis-sessions", {"sessions": sessions})

    def read_changelog(self) -> list[dict[str, Any]]:
        """System-improvement changelog (HU-009-JarvisMode, SPEC_JARVIS.md
        §10) — storage/changelog.json, shape {"entries": [...]}. Exposed flat
        (same convention as read_mar_memory)."""
        wrapper = self._read_dict("changelog")
        entries = wrapper.get("entries")
        return entries if isinstance(entries, list) else []

    def write_changelog(self, entries: list[dict[str, Any]]) -> None:
        self._write_dict("changelog", {"entries": entries})

    def _read_dict(self, name: str) -> dict[str, Any]:
        if self.using_kv and self._redis is not None:
            try:
                value = self._redis.get(name)
                if value is None:
                    return {}
                # See _read_list's comment above — upstash_redis's client
                # returns a raw JSON string on .get(), never auto-parsed.
                if isinstance(value, str):
                    return json.loads(value)
                return value
            except Exception as error:  # noqa: BLE001 - a flaky KV call must not 500 the whole route
                print(f'storage.py: Redis read_dict("{name}") failed: {error}')
                return {}
        try:
            file_path = self._file_path(name)
            if not file_path.exists():
                return {}
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f'storage.py: read_dict("{name}") failed: {error}')
            return {}

    def _write_dict(self, name: str, value: dict[str, Any]) -> None:
        if self.using_kv and self._redis is not None:
            try:
                self._redis.set(name, value)
            except Exception as error:  # noqa: BLE001 - a flaky KV call must not 500 the whole route
                print(f'storage.py: Redis write_dict("{name}") failed: {error}')
            return
        try:
            self._file_path(name).write_text(
                json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as error:
            print(f'storage.py: write_dict("{name}") failed: {error}')


_storage: Storage | None = None


def get_storage() -> Storage:
    """Returns the process-wide Storage instance, constructing it on first use.

    Not an lru_cache-wrapped function: Storage's constructor has side effects
    (mkdir, opening a Redis client) that should run exactly once per process
    but be easy to reset in tests via `app.core.storage._storage = None`.
    """
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage
