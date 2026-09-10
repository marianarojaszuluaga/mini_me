from __future__ import annotations

AUTH = {"Authorization": "Bearer test-api-key"}


def test_register_commitment_and_read_velocity(client):
    resp = client.post(
        "/projects/proj-1/velocity/commitments",
        json={
            "project_id": "proj-1",
            "week_start": "2026-09-07",
            "committed_items": 10,
            "completed_items": 7,
        },
        headers=AUTH,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated_existing"] is False

    series = client.get("/projects/proj-1/velocity", headers=AUTH)
    assert series.status_code == 200
    body = series.json()
    assert body["project_id"] == "proj-1"
    assert len(body["points"]) == 1
    point = body["points"][0]
    assert point["committed_items"] == 10
    assert point["completed_items"] == 7
    assert point["rollover"] == 3
    assert abs(point["completion_rate"] - 0.7) < 1e-9


def test_register_commitment_is_idempotent_on_same_week(client):
    payload = {
        "project_id": "proj-2",
        "week_start": "2026-09-07",
        "committed_items": 5,
        "completed_items": 5,
    }
    first = client.post("/projects/proj-2/velocity/commitments", json=payload, headers=AUTH)
    assert first.json()["updated_existing"] is False

    payload["completed_items"] = 2
    second = client.post("/projects/proj-2/velocity/commitments", json=payload, headers=AUTH)
    assert second.status_code == 200
    assert second.json()["updated_existing"] is True

    series = client.get("/projects/proj-2/velocity", headers=AUTH)
    points = series.json()["points"]
    # Same week posted twice -> exactly one row, with the latest value.
    assert len(points) == 1
    assert points[0]["completed_items"] == 2
    assert points[0]["rollover"] == 3


def test_velocity_requires_auth(client):
    resp = client.get("/projects/proj-1/velocity")
    assert resp.status_code in (401, 403)


def test_commitment_project_id_mismatch_rejected(client):
    resp = client.post(
        "/projects/proj-1/velocity/commitments",
        json={"project_id": "other", "week_start": "2026-09-07", "committed_items": 1},
        headers=AUTH,
    )
    assert resp.status_code == 400
