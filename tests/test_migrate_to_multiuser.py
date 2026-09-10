from __future__ import annotations

from app.core.storage import get_storage
from scripts.migrate_to_multiuser import run_migration


def _seed_projects(storage, n=2, with_owner=False):
    projects = []
    for i in range(n):
        p = {"id": f"proj-{i}", "name": f"Project {i}"}
        if with_owner:
            p["owner_user_id"] = "someone-else"
        projects.append(p)
    storage.write_projects(projects)
    return projects


def _seed_auth_profiles(storage, n=2, with_user=False):
    profiles = []
    for i in range(n):
        p = {"id": f"auth-{i}", "provider": "github"}
        if with_user:
            p["user_id"] = "someone-else"
        profiles.append(p)
    storage.write_auth_profiles(profiles)
    return profiles


def test_migration_assigns_all_projects_and_profiles():
    storage = get_storage()
    _seed_projects(storage, n=3)
    _seed_auth_profiles(storage, n=2)

    result = run_migration(
        storage, email="rojaszuluagamariana@gmail.com", password="s3cret-pass", name="Mariana"
    )

    assert result["projects_changed"] == 3
    assert result["auth_profiles_changed"] == 2

    projects = storage.read_projects()
    assert all(p["owner_user_id"] == result["user_id"] for p in projects)

    profiles = storage.read_auth_profiles()
    assert all(p["user_id"] == result["user_id"] for p in profiles)


def test_migration_is_idempotent():
    storage = get_storage()
    _seed_projects(storage, n=2)
    _seed_auth_profiles(storage, n=2)

    first = run_migration(
        storage, email="rojaszuluagamariana@gmail.com", password="s3cret-pass", name="Mariana"
    )
    second = run_migration(
        storage, email="rojaszuluagamariana@gmail.com", password="s3cret-pass", name="Mariana"
    )

    assert first["user_id"] == second["user_id"]
    # Second run finds no unassigned records left to touch.
    assert second["projects_changed"] == 0
    assert second["auth_profiles_changed"] == 0


def test_migration_does_not_overwrite_existing_ownership():
    storage = get_storage()
    _seed_projects(storage, n=2, with_owner=True)
    _seed_auth_profiles(storage, n=2, with_user=True)

    result = run_migration(
        storage, email="rojaszuluagamariana@gmail.com", password="s3cret-pass", name="Mariana"
    )

    assert result["projects_changed"] == 0
    assert result["auth_profiles_changed"] == 0

    projects = storage.read_projects()
    assert all(p["owner_user_id"] == "someone-else" for p in projects)
