"""
Pydantic model for an Auth Profile — SPEC_JARVIS.md §6.2 / §3 of
ARCHITECTURE_JARVIS.md.

An Auth Profile is a named identity (provider + account + scope) Mar already
has, kept separate from any single Project so the same identity can be
reused to connect repos across projects. The real token is NEVER stored
here — `token_ref` points at an env var or a secret store, same principle as
`Repository.accessTokenRef` in app/schemas/project.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AuthProfile(BaseModel):
    id: str
    provider: Literal["github", "bitbucket"]
    account: str
    # Free-form label, e.g. "personal-github", "org:imagineappsdev" —
    # matches the storage/auth-profiles.json shape already sketched in
    # SPEC_JARVIS.md §6.2.
    scope: str | None = None
    # Never the token in clear text — env var name or secret-store reference.
    token_ref: str | None = None
    createdAt: str = Field(default_factory=_now_iso)


class AuthProfileCreateRequest(BaseModel):
    provider: Literal["github", "bitbucket"]
    account: str
    scope: str | None = None
    token_ref: str | None = None
