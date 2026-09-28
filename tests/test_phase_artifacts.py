"""
Gaps de la auditoría de flujos de Mini me (artefacto "Flujos de Mini me",
sección 03 "Ciclo de vida", 2026-09-26):

1. GET /projects/{id}/phase-artifacts — no existía ninguna forma de listar
   resultados ya subidos sin ir directo al repo a mano.
2. POST /projects/{id}/phase-artifact/{artifact_id}/feedback — no existía
   forma de marcar un resultado como "no sirvió" con una corrección.
3. agent_registry.build_brain_context — el Project Brain (decisionLog,
   alerts, backlog HU, services) no llegaba nunca al context de un agente.
"""

from __future__ import annotations

import json

from app.services import agent_registry


def _seed_project_with_artifact(client, headers):
    create = client.post("/projects", json={"name": "Proyecto Artifacts Test"}, headers=headers)
    project_id = create.json()["id"]

    import app.core.storage as storage_module

    storage = storage_module.get_storage()
    projects = storage.read_projects()
    project = next(p for p in projects if p["id"] == project_id)
    project.setdefault("memory", {}).setdefault("phaseArtifacts", []).append(
        {
            "id": "artifact-1",
            "phase": "planning",
            "agent": "gime",
            "filename": "gime-1.md",
            "repoPath": "01-Planning/gime-1.md",
            "input": "HU original",
            "output": "resultado de gime",
            "status": "activated",
            "correctionOf": None,
            "correctionNote": None,
            "createdAt": "2026-09-26T00:00:00Z",
            "createdBy": None,
        }
    )
    storage.write_projects(projects)
    return project_id


def test_list_phase_artifacts_returns_seeded_entry(client):
    headers = {"Authorization": "Bearer test-api-key"}
    project_id = _seed_project_with_artifact(client, headers)

    response = client.get(f"/projects/{project_id}/phase-artifacts", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == "artifact-1"
    assert body[0]["agent"] == "gime"


def test_list_phase_artifacts_filters_by_phase(client):
    headers = {"Authorization": "Bearer test-api-key"}
    project_id = _seed_project_with_artifact(client, headers)

    matching = client.get(f"/projects/{project_id}/phase-artifacts?phase=planning", headers=headers)
    assert len(matching.json()) == 1

    other = client.get(f"/projects/{project_id}/phase-artifacts?phase=backend", headers=headers)
    assert other.json() == []


def test_submit_feedback_marks_rejected_with_note(client):
    headers = {"Authorization": "Bearer test-api-key"}
    project_id = _seed_project_with_artifact(client, headers)

    response = client.post(
        f"/projects/{project_id}/phase-artifact/artifact-1/feedback",
        json={"correctionNote": "Faltó cubrir el caso de error 404"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "rejected"
    assert body["correctionNote"] == "Faltó cubrir el caso de error 404"

    fetched = client.get(f"/projects/{project_id}/phase-artifacts", headers=headers).json()
    assert fetched[0]["status"] == "rejected"


def test_submit_feedback_requires_correction_note(client):
    headers = {"Authorization": "Bearer test-api-key"}
    project_id = _seed_project_with_artifact(client, headers)

    response = client.post(
        f"/projects/{project_id}/phase-artifact/artifact-1/feedback",
        json={},
        headers=headers,
    )
    assert response.status_code == 400


def test_upload_phase_artifact_without_repo_records_draft_without_commit(client):
    """Bug encontrado en verificación en vivo (2026-09-28): el flujo de
    "no sirvió" necesita registrar el resultado incluso en proyectos sin
    repo conectado todavía — antes de commitToRepo, esto devolvía 400
    ("Project has no connected repository") y bloqueaba el feedback."""
    headers = {"Authorization": "Bearer test-api-key"}
    create = client.post("/projects", json={"name": "Proyecto Sin Repo"}, headers=headers)
    project_id = create.json()["id"]

    response = client.post(
        f"/projects/{project_id}/phase-artifact",
        json={
            "phase": "planning",
            "filename": "gime-1.md",
            "content": "resultado",
            "agent": "gime",
            "commitToRepo": False,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["path"] is None
    assert body["artifactId"]

    listed = client.get(f"/projects/{project_id}/phase-artifacts", headers=headers).json()
    assert listed[0]["status"] == "draft"
    assert listed[0]["repoPath"] is None


def test_upload_phase_artifact_with_commit_to_repo_still_requires_repo(client):
    headers = {"Authorization": "Bearer test-api-key"}
    create = client.post("/projects", json={"name": "Proyecto Sin Repo 2"}, headers=headers)
    project_id = create.json()["id"]

    response = client.post(
        f"/projects/{project_id}/phase-artifact",
        json={
            "phase": "planning",
            "filename": "gime-1.md",
            "content": "resultado",
            "agent": "gime",
            "commitToRepo": True,
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_submit_feedback_unknown_artifact_404s(client):
    headers = {"Authorization": "Bearer test-api-key"}
    project_id = _seed_project_with_artifact(client, headers)

    response = client.post(
        f"/projects/{project_id}/phase-artifact/does-not-exist/feedback",
        json={"correctionNote": "x"},
        headers=headers,
    )
    assert response.status_code == 404


def test_build_brain_context_includes_decisions_alerts_backlog_and_services():
    project = {
        "memory": {
            "projectBrain": {
                "decisionLog": [{"decision": "Usar Postgres"}],
                "alerts": [{"alert": "Falta token de Basecamp", "status": "open"}],
                "services": [
                    {"id": "qa_automated", "enabled": True},
                    {"id": "basecamp_sync", "enabled": False},
                ],
            },
            "backlogs": {"hu": {"ids": ["HU-001", "HU-002"]}},
        }
    }

    context = agent_registry.build_brain_context(project)
    assert context["decisionLog"] == [{"decision": "Usar Postgres"}]
    assert context["alerts"] == [{"alert": "Falta token de Basecamp", "status": "open"}]
    assert context["backlogHuIds"] == ["HU-001", "HU-002"]
    assert context["enabledServices"] == ["qa_automated"]


def test_build_brain_context_handles_missing_memory():
    assert agent_registry.build_brain_context({}) == {
        "decisionLog": [],
        "alerts": [],
        "backlogHuIds": [],
        "enabledServices": [],
    }


def test_build_brain_context_truncates_when_oversized():
    huge_decision_log = [{"decision": f"decisión número {i}" * 20} for i in range(200)]
    project = {"memory": {"projectBrain": {"decisionLog": huge_decision_log}}}

    context = agent_registry.build_brain_context(project)
    assert len(json.dumps(context)) < 1000
    assert context["decisionLogCount"] == 200
    assert "note" in context
