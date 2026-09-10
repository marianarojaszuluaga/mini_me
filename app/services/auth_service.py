"""
User authentication service — multi-usuario (2026-09-09).

Two login paths, one JWT:
- email + password: bcrypt hash via passlib.
- Google OAuth (app login): verifies the Google id_token server-side, then
  either logs in an existing user (matched by google_id or by email) or
  creates one. Uses google-auth's id_token verifier when available; falls
  back to a plain JWT-claims decode (no signature check against Google's
  keys) ONLY if google-auth isn't installed, clearly logged as such so this
  never silently looks more secure than it is.

JWT: signed with settings.JWT_SECRET (HS256), via python-jose (already a
project dependency-of-choice per requirements — see pyproject additions).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import Settings, get_settings
from app.core.storage import Storage, get_storage
from app.schemas.user import User

_bearer_scheme = HTTPBearer(auto_error=False)

# bcrypt truncates/ignores anything past 72 bytes internally anyway (and
# recent bcrypt releases raise instead of silently truncating) — enforced
# explicitly here rather than depending on passlib's CryptContext, whose
# bcrypt backend self-test trips over that same 72-byte limit on some
# bcrypt versions (observed: ValueError during backend detection).
_MAX_PASSWORD_BYTES = 72

JWT_ALGORITHM = "HS256"
JWT_EXPIRES_SECONDS = 60 * 60 * 24 * 7  # 7 days


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    truncated = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.checkpw(truncated, password_hash.encode("ascii"))


def _find_user(users: list[dict[str, Any]], **filters: Any) -> dict[str, Any] | None:
    for user in users:
        if all(user.get(key) == value for key, value in filters.items()):
            return user
    return None


def get_user_by_email(storage: Storage, email: str) -> dict[str, Any] | None:
    return _find_user(storage.read_users(), email=email.lower())


def get_user_by_id(storage: Storage, user_id: str) -> dict[str, Any] | None:
    return _find_user(storage.read_users(), id=user_id)


def create_user(
    storage: Storage,
    email: str,
    password: str | None = None,
    name: str | None = None,
    google_id: str | None = None,
    role: str = "owner",
) -> User:
    email = email.lower()
    if get_user_by_email(storage, email):
        raise AuthError(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        name=name,
        password_hash=hash_password(password) if password else None,
        google_id=google_id,
        role=role,  # type: ignore[arg-type]
    )
    users = storage.read_users()
    users.append(user.model_dump())
    storage.write_users(users)
    return user


def authenticate_with_password(storage: Storage, email: str, password: str) -> User:
    record = get_user_by_email(storage, email)
    if not record or not record.get("password_hash"):
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not verify_password(password, record["password_hash"]):
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return User(**record)


def verify_google_id_token(id_token_str: str, settings: Settings) -> dict[str, Any]:
    """Verifies a Google id_token and returns its claims (sub, email, name).

    Uses google-auth's real verifier (checks signature against Google's
    public keys + audience) when the package + GOOGLE_OAUTH_CLIENT_ID are
    available. Otherwise raises — we never accept an unverified token as a
    login credential.
    """
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise AuthError(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Google login not configured on the server (google-auth not installed)",
        ) from exc

    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise AuthError(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Google login not configured on the server (GOOGLE_OAUTH_CLIENT_ID missing)",
        )

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID
        )
    except ValueError as exc:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid Google token") from exc
    return claims


def login_or_create_google_user(storage: Storage, claims: dict[str, Any]) -> User:
    google_id = claims.get("sub")
    email = (claims.get("email") or "").lower()
    if not google_id or not email:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Google token missing sub/email")

    record = _find_user(storage.read_users(), google_id=google_id) or get_user_by_email(
        storage, email
    )
    if record:
        if not record.get("google_id"):
            record["google_id"] = google_id
            users = storage.read_users()
            for u in users:
                if u["id"] == record["id"]:
                    u["google_id"] = google_id
            storage.write_users(users)
        return User(**record)

    return create_user(
        storage,
        email=email,
        name=claims.get("name"),
        google_id=google_id,
    )


def create_access_token(user: User, settings: Settings) -> str:
    now = int(time.time())
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + JWT_EXPIRES_SECONDS,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    storage: Storage = Depends(get_storage),
) -> User:
    """FastAPI dependency: validates a user JWT (NOT an APP_API_KEYS token) and
    returns the corresponding User. Use on routes that need real per-user
    ownership (projects, repositories) — `authenticate_token` (API keys)
    stays available separately for server-to-server calls."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No token provided")

    try:
        payload = decode_access_token(credentials.credentials, settings)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    record = get_user_by_id(storage, payload.get("sub", ""))
    if not record:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return User(**record)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    storage: Storage = Depends(get_storage),
) -> User | None:
    """Like get_current_user, but returns None instead of raising when no
    (valid) user JWT is present — lets project/repository routes filter by
    owner when a real user is logged in while staying backward-compatible
    with existing APP_API_KEYS-only server-to-server callers."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials, settings)
    except AuthError:
        return None
    record = get_user_by_id(storage, payload.get("sub", ""))
    return User(**record) if record else None
