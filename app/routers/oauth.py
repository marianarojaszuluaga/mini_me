"""
Real OAuth Authorization Code flow for Auth Profiles — SPEC_JARVIS.md §11,
resolved 2026-08-14 in response to Mariana's "SÍ QUE SEA REAL" (item 2) and
"AMBOS" (item 1: support Google SSO alongside direct GitHub/Bitbucket OAuth).

This replaces the manual stand-in form in IntegrationsDrillDown.jsx's
"Conectar con ..." buttons for providers whose OAuth App is configured
(app/core/config.py's GITHUB/BITBUCKET/GOOGLE_OAUTH_CLIENT_ID/SECRET) — the
manual form stays as a fallback for providers without one (e.g. basecamp).

Two endpoints per provider:
- GET /auth-profiles/oauth/{provider}/start — redirects the browser to the
  provider's real authorize URL. Can't carry the app's Bearer token on a
  top-level navigation, so it authenticates via `?app_key=` query param
  instead (checked with the same constant-time compare as the header path).
- GET /auth-profiles/oauth/{provider}/callback — the provider redirects here
  with `code`/`state`; exchanges the code for a real token via httpx,
  fetches the account identity, upserts an AuthProfile (auth_profiles.
  upsert_oauth_profile), then redirects the browser back to the dashboard.

`state` is a short-lived, single-use CSRF token (in-memory, since a single
uvicorn process backs local dev and each Vercel invocation is stateless —
acceptable for now: OAuth flows complete within seconds of being issued,
this exists to block CSRF, not to be a large durable store).
"""

from __future__ import annotations

import secrets
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.services import auth_profiles

router = APIRouter()

_STATE_TTL_SECONDS = 600
_pending_states: dict[str, float] = {}


def _new_state() -> str:
    token = secrets.token_urlsafe(24)
    _pending_states[token] = time.time() + _STATE_TTL_SECONDS
    return token


def _consume_state(token: str) -> bool:
    expires_at = _pending_states.pop(token, None)
    return expires_at is not None and expires_at >= time.time()


def _check_app_key(app_key: str) -> None:
    settings = get_settings()
    allowed = settings.allowed_api_keys
    if not allowed or not any(secrets.compare_digest(app_key, key) for key in allowed):
        raise HTTPException(status_code=403, detail="Invalid app_key")


class _ProviderConfig:
    def __init__(self, authorize_url: str, token_url: str, scope: str, extra_authorize_params: dict[str, str] | None = None):
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.scope = scope
        self.extra_authorize_params = extra_authorize_params or {}


_PROVIDER_CONFIGS: dict[str, _ProviderConfig] = {
    "github": _ProviderConfig(
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        scope="repo read:org",
    ),
    "bitbucket": _ProviderConfig(
        authorize_url="https://bitbucket.org/site/oauth2/authorize",
        token_url="https://bitbucket.org/site/oauth2/access_token",
        scope="repository account",
    ),
    "google": _ProviderConfig(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scope="openid email profile",
        extra_authorize_params={"access_type": "offline", "prompt": "consent"},
    ),
}


def _client_credentials(provider: str) -> tuple[str, str]:
    settings = get_settings()
    client_id, client_secret = {
        "github": (settings.GITHUB_OAUTH_CLIENT_ID, settings.GITHUB_OAUTH_CLIENT_SECRET),
        "bitbucket": (settings.BITBUCKET_OAUTH_CLIENT_ID, settings.BITBUCKET_OAUTH_CLIENT_SECRET),
        "google": (settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET),
    }[provider]
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=501,
            detail=(
                f"OAuth App for '{provider}' is not configured yet — set "
                f"{provider.upper()}_OAUTH_CLIENT_ID/{provider.upper()}_OAUTH_CLIENT_SECRET. "
                "See SPEC_JARVIS.md §11."
            ),
        )
    return client_id, client_secret


def _redirect_uri(provider: str) -> str:
    settings = get_settings()
    return f"{settings.BACKEND_PUBLIC_URL}/auth-profiles/oauth/{provider}/callback"


@router.get("/auth-profiles/oauth/{provider}/start")
async def oauth_start(provider: str, app_key: str = Query(...)) -> RedirectResponse:
    if provider not in _PROVIDER_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")
    _check_app_key(app_key)
    client_id, _ = _client_credentials(provider)
    config = _PROVIDER_CONFIGS[provider]
    state = _new_state()

    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(provider),
        "scope": config.scope,
        "state": state,
        "response_type": "code",
        **config.extra_authorize_params,
    }
    url = httpx.URL(config.authorize_url, params=params)
    return RedirectResponse(url=str(url))


async def _exchange_code(provider: str, code: str) -> dict[str, Any]:
    config = _PROVIDER_CONFIGS[provider]
    client_id, client_secret = _client_credentials(provider)
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": _redirect_uri(provider),
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(config.token_url, data=payload, headers={"Accept": "application/json"})
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"OAuth token exchange failed ({provider}): {response.text}")
    return response.json()


async def _fetch_account(provider: str, access_token: str) -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        if provider == "github":
            resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
            )
            resp.raise_for_status()
            return resp.json()["login"]
        if provider == "bitbucket":
            resp = await client.get(
                "https://api.bitbucket.org/2.0/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()["username"]
        if provider == "google":
            resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()["email"]
    raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")


@router.get("/auth-profiles/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    frontend_integrations_url = f"{settings.FRONTEND_URL}/?integrations=oauth"

    if provider not in _PROVIDER_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")
    if error:
        return RedirectResponse(url=f"{frontend_integrations_url}&status=error&reason={error}")
    if not code or not state or not _consume_state(state):
        return RedirectResponse(url=f"{frontend_integrations_url}&status=error&reason=invalid_state")

    token_response = await _exchange_code(provider, code)
    access_token = token_response.get("access_token")
    if not access_token:
        return RedirectResponse(url=f"{frontend_integrations_url}&status=error&reason=no_access_token")

    account = await _fetch_account(provider, access_token)
    config = _PROVIDER_CONFIGS[provider]

    auth_profiles.upsert_oauth_profile(
        provider=provider,
        account=account,
        scope=token_response.get("scope") or config.scope,
        access_token=access_token,
        refresh_token=token_response.get("refresh_token"),
        token_expires_at=None,
    )

    return RedirectResponse(url=f"{frontend_integrations_url}&status=success&provider={provider}&account={account}")
