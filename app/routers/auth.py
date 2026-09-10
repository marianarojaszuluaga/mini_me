"""
POST /auth/register, POST /auth/login, POST /auth/google, GET /auth/me —
multi-usuario (2026-09-09). See app/services/auth_service.py for the
password/JWT/Google logic and app/schemas/user.py for the models.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.storage import Storage, get_storage
from app.schemas.user import (
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    User,
    UserPublic,
)
from app.services import auth_service
from app.services.auth_service import AuthError, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User, settings: Settings) -> TokenResponse:
    token = auth_service.create_access_token(user, settings)
    return TokenResponse(access_token=token, user=UserPublic.from_user(user))


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        user = auth_service.create_user(
            storage, email=body.email, password=body.password, name=body.name
        )
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return _token_response(user, settings)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        user = auth_service.authenticate_with_password(storage, body.email, body.password)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return _token_response(user, settings)


@router.post("/google", response_model=TokenResponse)
async def google_login(
    body: GoogleLoginRequest,
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        claims = auth_service.verify_google_id_token(body.id_token, settings)
        user = auth_service.login_or_create_google_user(storage, claims)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return _token_response(user, settings)


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.from_user(current_user)
