"""
Optional project-creation fields (2026-09-28, task_21c4faa0 — Mariana: "se
puede construir un formulario más completo... alcance: un archivo adjunto,
fecha inicio y fecha fin, Cliente, y exponer un endpoint que permita que
API a API se puedan crear proyectos"). POST /projects already accepts a
pure API key (authenticate_api_key_or_user with current_user=None) — no new
route was needed, this suite just pins the new optional fields.
"""

from __future__ import annotations


def test_create_project_with_all_optional_fields(client):
    headers = {"Authorization": "Bearer test-api-key"}
    response = client.post(
        "/projects",
        json={
            "name": "Proyecto Completo",
            "client": "Finanz Butik",
            "startDate": "2026-10-01",
            "endDate": "2026-12-15",
            "scopeAttachment": {"filename": "alcance.md", "content": "# Alcance\n\nMVP."},
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["client"] == "Finanz Butik"
    assert body["startDate"] == "2026-10-01"
    assert body["endDate"] == "2026-12-15"
    assert body["scopeAttachment"]["filename"] == "alcance.md"
    assert body["scopeAttachment"]["content"] == "# Alcance\n\nMVP."
    assert "uploadedAt" in body["scopeAttachment"]


def test_create_project_without_optional_fields_defaults_to_none(client):
    headers = {"Authorization": "Bearer test-api-key"}
    response = client.post("/projects", json={"name": "Proyecto Minimo"}, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["client"] is None
    assert body["startDate"] is None
    assert body["endDate"] is None
    assert body["scopeAttachment"] is None


def test_create_project_is_api_key_only_callable_without_user_jwt(client):
    """The existing POST /projects endpoint IS the API-to-API endpoint —
    authenticate_api_key_or_user already accepts a bare API key with no
    user JWT (current_user resolves to None), so no separate route was
    needed for external/server-to-server project creation."""
    headers = {"Authorization": "Bearer test-api-key"}
    response = client.post(
        "/projects",
        json={"name": "Proyecto Externo", "client": "Cliente API"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["client"] == "Cliente API"
