"""
Real DoD/checklist per phase (2026-09-26, Mariana: "revisar los DoD de cada
fase y la evidencia para cerrarla... el checklist debe mostrar completitud y
alimentar el dashboard"). Replaces the old "+15 per agent invocation, cap 95"
progress heuristic — this suite pins that progress is now a real function of
checklist completion, backed by a real endpoint, not an arbitrary counter.
"""

from __future__ import annotations

from app.routers.projects import _default_phase_checklists_dict, _recompute_progress


def test_default_checklists_match_real_phase_outputs():
    from app.phases.phase_contracts import list_phases

    checklists = _default_phase_checklists_dict()
    for phase in list_phases():
        assert phase["key"] in checklists
        assert len(checklists[phase["key"]]) == len(phase.get("outputs", []))
        for item, output in zip(checklists[phase["key"]], phase["outputs"]):
            assert item["label"] == output
            assert item["done"] is False


def test_recompute_progress_from_checklist_state():
    project = {
        "currentPhase": 1,
        "memory": {"phaseChecklists": _default_phase_checklists_dict()},
    }
    # planning has 7 outputs — mark 2 done, expect ~29%.
    checklist = project["memory"]["phaseChecklists"]["planning"]
    checklist[0]["done"] = True
    checklist[1]["done"] = True
    assert _recompute_progress(project) == round(2 / 7 * 100)


def test_recompute_progress_falls_back_when_no_checklist_for_phase():
    project = {"currentPhase": 1, "progress": 42, "memory": {"phaseChecklists": {}}}
    assert _recompute_progress(project) == 42


def test_toggle_checklist_item_endpoint_updates_progress(client):
    headers = {"Authorization": "Bearer test-api-key"}
    create = client.post("/projects", json={"name": "Proyecto DoD Test"}, headers=headers)
    assert create.status_code == 201
    project_id = create.json()["id"]

    backend_checklist = create.json()["memory"]["phaseChecklists"]["backend"]
    assert len(backend_checklist) == 3  # backend phase has 3 real outputs
    item_id = backend_checklist[0]["id"]

    response = client.patch(
        f"/projects/{project_id}/phase-checklist/backend/{item_id}",
        json={"done": True, "evidence": "PR #42 merged"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["item"]["done"] is True
    assert body["item"]["evidence"] == "PR #42 merged"
    assert body["item"]["completedAt"] is not None

    # currentPhase is still 1 (planning) at creation — backend checklist
    # changes don't move progress until currentPhase actually reaches it.
    fetched = client.get(f"/projects/{project_id}", headers=headers).json()
    assert fetched["memory"]["phaseChecklists"]["backend"][0]["done"] is True


def test_toggle_checklist_item_unknown_phase_key_404s(client):
    headers = {"Authorization": "Bearer test-api-key"}
    create = client.post("/projects", json={"name": "Proyecto DoD 404"}, headers=headers)
    project_id = create.json()["id"]

    response = client.patch(
        f"/projects/{project_id}/phase-checklist/not_a_phase/whatever",
        json={"done": True},
        headers=headers,
    )
    assert response.status_code == 404
