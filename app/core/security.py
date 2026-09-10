"""
Auth dependency — replaces middleware/auth.js's authenticateToken.

Validates a Bearer token against APP_API_KEYS with a constant-time compare
(secrets.compare_digest), same semantics as the Node version:
- 500 if APP_API_KEYS is not configured at all (server misconfigured)
- 401 if no token is provided
- 403 if the token doesn't match any allowed key
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

# auto_error=False so a missing header surfaces as our own 401 message
# instead of FastAPI's generic "Not authenticated".
_bearer_scheme = HTTPBearer(auto_error=False)


def _timing_safe_equal(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


async def authenticate_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """FastAPI dependency: returns the validated token, or raises HTTPException."""
    allowed_keys = settings.allowed_api_keys

    if not allowed_keys:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: no API keys configured",
        )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No token provided",
        )

    token = credentials.credentials
    is_valid = any(_timing_safe_equal(token, key) for key in allowed_keys)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token",
        )

    return token


async def authenticate_api_key_or_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """Multi-usuario (2026-09-09): accepts EITHER a shared APP_API_KEYS token
    (server-to-server / admin callers, `authenticate_token`'s old behavior)
    OR a valid per-user JWT (app/services/auth_service.create_access_token).
    Used as the router-level dependency for user-facing routes (projects,
    repositories) so end users authenticate with their own JWT while
    existing API-key-only callers keep working unchanged.

    Route handlers that need to know the actual user (for per-user
    filtering) should ALSO depend on
    `app.services.auth_service.get_current_user_optional` — this dependency
    only gates access, it doesn't identify who's calling.
    """
    if credentials is not None and credentials.credentials:
        allowed_keys = settings.allowed_api_keys
        if allowed_keys and any(
            _timing_safe_equal(credentials.credentials, key) for key in allowed_keys
        ):
            return credentials.credentials

        # Not a valid API key — try it as a user JWT instead.
        from app.services.auth_service import AuthError, decode_access_token

        try:
            decode_access_token(credentials.credentials, settings)
            return credentials.credentials
        except AuthError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No valid API key or user token provided",
    )
