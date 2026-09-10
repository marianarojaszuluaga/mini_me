"""
Pydantic models for User — multi-usuario (SPEC_JARVIS.md, "Multi-usuario e
Internacionalización (2026-09-09)").

Two ways a User can authenticate (see app/services/auth_service.py):
- email + password: `password_hash` set (bcrypt via passlib), `google_id` None.
- Google OAuth (app login, NOT the integration Auth Profile in
  app/schemas/auth_profile.py): `google_id` set, `password_hash` may be None
  if the account was created purely via Google sign-in.

`UserPublic` is what ever leaves the API — never `password_hash`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


Role = Literal["owner", "admin", "member"]


class User(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None
    password_hash: str | None = None
    google_id: str | None = None
    role: Role = "owner"
    createdAt: str = Field(default_factory=_now_iso)


class UserPublic(BaseModel):
    """Same as User, minus password_hash — safe to return from the API."""

    id: str
    email: EmailStr
    name: str | None = None
    role: Role = "owner"
    createdAt: str

    @classmethod
    def from_user(cls, user: User) -> "UserPublic":
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            createdAt=user.createdAt,
        )


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    # Google Identity Services id_token (JWT) from the frontend's "Continuar
    # con Google" button — verified server-side against Google's public keys.
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserPublic
