from __future__ import annotations

from unittest.mock import patch


def test_register_and_me(client):
    resp = client.post(
        "/auth/register",
        json={"email": "mariana@example.com", "password": "supersecret1", "name": "Mariana"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == "mariana@example.com"
    assert "password_hash" not in body["user"]
    token = body["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "mariana@example.com"


def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "password": "supersecret1"}
    first = client.post("/auth/register", json=payload)
    assert first.status_code == 200
    second = client.post("/auth/register", json=payload)
    assert second.status_code == 409


def test_login_with_correct_password(client):
    client.post(
        "/auth/register", json={"email": "login@example.com", "password": "supersecret1"}
    )
    resp = client.post(
        "/auth/login", json={"email": "login@example.com", "password": "supersecret1"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_with_wrong_password_rejected(client):
    client.post(
        "/auth/register", json={"email": "login2@example.com", "password": "supersecret1"}
    )
    resp = client.post(
        "/auth/login", json={"email": "login2@example.com", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_me_without_token_rejected(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_google_login_mocked(client):
    fake_claims = {"sub": "google-123", "email": "googleuser@example.com", "name": "G User"}
    with patch(
        "app.services.auth_service.verify_google_id_token", return_value=fake_claims
    ):
        resp = client.post("/auth/google", json={"id_token": "fake-token"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == "googleuser@example.com"

    # Logging in again with the same google claims reuses the same user
    # (no duplicate created) rather than erroring.
    with patch(
        "app.services.auth_service.verify_google_id_token", return_value=fake_claims
    ):
        resp2 = client.post("/auth/google", json={"id_token": "fake-token"})
    assert resp2.status_code == 200
    assert resp2.json()["user"]["id"] == body["user"]["id"]


def test_projects_are_isolated_per_user(client):
    def register(email):
        r = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
        return r.json()["access_token"]

    token_a = register("usera@example.com")
    token_b = register("userb@example.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    created = client.post(
        "/projects", json={"name": "Proyecto de A"}, headers=headers_a
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    list_a = client.get("/projects", headers=headers_a)
    assert any(p["id"] == project_id for p in list_a.json())

    list_b = client.get("/projects", headers=headers_b)
    assert all(p["id"] != project_id for p in list_b.json())

    # User B can't fetch user A's project by id either.
    get_b = client.get(f"/projects/{project_id}", headers=headers_b)
    assert get_b.status_code == 404
