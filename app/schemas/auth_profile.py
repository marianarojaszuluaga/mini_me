"""
Pydantic model for an Auth Profile — SPEC_JARVIS.md §6.2 / §3 of
ARCHITECTURE_JARVIS.md.

An Auth Profile is a named identity (provider + account + scope) Mar already
has, kept separate from any single Project so the same identity can be
reused to connect repos across projects.

Two ways a profile gets created (SPEC_JARVIS.md §11, resolved 2026-08-14):
- `auth_method="manual"`: the original stand-in form — `token_ref` points at
  an env var / secret store, same principle as `Repository.accessTokenRef`.
- `auth_method="oauth"`: a real Authorization Code flow (app/routers/oauth.py)
  — `access_token`/`refresh_token`/`token_expires_at` hold the real OAuth
  token issued by the provider. These are set by the server after the OAuth
  callback and are NEVER echoed back by GET /auth-profiles (see
  `to_public_dict` below) — the frontend only ever needs to know a profile
  exists and which account/scope it covers, not the token itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Provider = Literal["github", "bitbucket", "google"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AuthProfile(BaseModel):
    id: str
    provider: Provider
    account: str
    # Free-form label, e.g. "personal-github", "org:imagineappsdev" —
    # matches the storage/auth-profiles.json shape already sketched in
    # SPEC_JARVIS.md §6.2.
    scope: str | None = None
    auth_method: Literal["manual", "oauth"] = "manual"
    # Manual path only — never the token in clear text, an env var name or
    # secret-store reference.
    token_ref: str | None = None
    # OAuth path only — the real tokens the provider issued. Server-side
    # only, stripped by to_public_dict() before anything reaches the API.
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: str | None = None
    createdAt: str = Field(default_factory=_now_iso)

    def to_public_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude={"access_token", "refresh_token"})


class AuthProfileCreateRequest(BaseModel):
    provider: Provider
    account: str
    scope: str | None = None
    token_ref: str | None = None
