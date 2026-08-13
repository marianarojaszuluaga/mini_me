"""
CRUD for Auth Profiles — SPEC_JARVIS.md §6.2. Plain list-in-a-file(/Redis
key), same pattern as everything else in app/core/storage.py.
"""

from __future__ import annotations

import time

from app.core.storage import get_storage
from app.schemas.auth_profile import AuthProfile, AuthProfileCreateRequest


def _new_profile_id(provider: str) -> str:
    return f"{provider}_{int(time.time() * 1000)}"


def list_auth_profiles() -> list[AuthProfile]:
    storage = get_storage()
    return [AuthProfile(**p) for p in storage.read_auth_profiles()]


def get_auth_profile(profile_id: str) -> AuthProfile | None:
    return next((p for p in list_auth_profiles() if p.id == profile_id), None)


def create_auth_profile(body: AuthProfileCreateRequest) -> AuthProfile:
    storage = get_storage()
    profiles = storage.read_auth_profiles()
    profile = AuthProfile(
        id=_new_profile_id(body.provider),
        provider=body.provider,
        account=body.account,
        scope=body.scope,
        token_ref=body.token_ref,
    )
    profiles.append(profile.model_dump())
    storage.write_auth_profiles(profiles)
    return profile


def delete_auth_profile(profile_id: str) -> bool:
    storage = get_storage()
    profiles = storage.read_auth_profiles()
    remaining = [p for p in profiles if p.get("id") != profile_id]
    if len(remaining) == len(profiles):
        return False
    storage.write_auth_profiles(remaining)
    return True
