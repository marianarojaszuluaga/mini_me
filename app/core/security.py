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
