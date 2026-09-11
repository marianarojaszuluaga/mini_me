"""Test del endpoint POST /projects/{id}/basecamp-cards/bulk (SPEC §5.4/§7.4)
con el parser genérico — mockea la llamada real a Basecamp
(app.services.basecamp_client.create_card), nunca pega a la red."""

from __future__ import annotations

from typing import Any

from app.routers import projects as projects_router


def _seed_project_and_auth_profile(client) -> None:
    from app.core.storage import get_storage

    storage = get_storage()
    storage.write_projects(
        [
            {
                "id": "p1",
                "name": "Proyecto Test",
                "basecamp": {"account_id": "acc1", "project_id": "bproj1"},
            }
        ]
    )
    storage.write_auth_profiles(
        [
            {
                "id": "ap1",
                "provider": "basecamp",
                "scope": "account_id:acc1",
                "account": "acc1",
                "access_token": "tok",
            }
        ]
    )


def test_bulk_create_generic_parser_creates_cards(client, monkeypatch):
    _seed_project_and_auth_profile(client)

    calls: list[dict[str, Any]] = []

    async def _fake_create_card(auth_profile, account_id, project_id, list_id, title, **kwargs):
        calls.append({"list_id": list_id, "title": title, **kwargs})
        return {"id": len(calls), "title": title}

    monkeypatch.setattr(projects_router, "create_card", _fake_create_card)

    body = {
        "rows": [
            {"column": "list-123", "title": "HU-1-Modulo: primero", "content": "desc", "date": "2026-10-01"},
            {"column": "list-123", "title": "HU-2-Modulo: segundo", "content": "desc2"},
            {"title": "sin columna"},  # debe fallar, no abortar el resto
        ]
    }
    response = client.post(
        "/projects/p1/basecamp-cards/bulk", json=body, headers={"Authorization": "Bearer test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data["created"]) == 2
    assert len(data["failed"]) == 1
    assert calls[0]["list_id"] == "list-123"
    assert calls[0]["title"] == "HU-1-Modulo: primero"
    assert calls[0]["due_on"] == "2026-10-01"


def test_bulk_create_preview_does_not_call_basecamp(client, monkeypatch):
    _seed_project_and_auth_profile(client)

    async def _boom(*args, **kwargs):
        raise AssertionError("preview no debe llamar a Basecamp")

    monkeypatch.setattr(projects_router, "create_card", _boom)

    body = {"rows": [{"column": "list-123", "title": "HU-1-Modulo: primero"}]}
    response = client.post(
        "/projects/p1/basecamp-cards/bulk/preview", json=body, headers={"Authorization": "Bearer test-api-key"}
    )
    assert response.status_code == 200
    assert response.json()["preview"][0]["title"] == "HU-1-Modulo: primero"


def test_bulk_create_missing_link_returns_501(client):
    from app.core.storage import get_storage

    get_storage().write_projects([{"id": "p2", "name": "Sin Basecamp"}])
    response = client.post(
        "/projects/p2/basecamp-cards/bulk",
        json={"rows": [{"column": "x", "title": "y"}]},
        headers={"Authorization": "Bearer test-api-key"},
    )
    assert response.status_code == 501
