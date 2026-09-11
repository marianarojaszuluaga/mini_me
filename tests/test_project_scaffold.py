"""
TAREA A (onboarding, 2026-09-11) — POST /projects/{id}/scaffold writes the
standard 6-folder structure into the project's connected repo. No real repo
is touched here: the adapter's create_or_update_file is monkeypatched to
just record calls, per the task's own instruction ("mockeado, no un repo
real").
"""

from __future__ import annotations

from app.services import project_scaffold


def test_scaffold_writes_six_expected_files(client, monkeypatch):
    calls: list[dict] = []

    async def fake_create_or_update_file(self, auth_profile, owner, repo, path, content, message, branch):
        calls.append({"owner": owner, "repo": repo, "path": path, "branch": branch})

    from app.services.repositories.github_adapter import GitHubAdapter

    monkeypatch.setattr(GitHubAdapter, "create_or_update_file", fake_create_or_update_file)

    headers = {"Authorization": "Bearer test-api-key"}
    create = client.post(
        "/projects",
        json={"name": "Proyecto Scaffold Test", "owner": "mariana"},
        headers=headers,
    )
    assert create.status_code == 201
    project_id = create.json()["id"]

    # Attach a connected repo directly via storage (no repositories router
    # dependency needed for this test).
    from app.core.storage import get_storage

    storage = get_storage()
    projects = storage.read_projects()
    project = next(p for p in projects if p["id"] == project_id)
    project["repositories"] = [
        {
            "id": "repo-1",
            "provider": "github",
            "owner": "mariana-org",
            "repo": "mini-me-demo",
            "defaultBranch": "main",
            "accessTokenRef": "env:GITHUB_TOKEN_TEST",
        }
    ]
    storage.write_projects(projects)

    response = client.post(f"/projects/{project_id}/scaffold", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    expected_paths = [f"{folder}/README.md" for folder, _, _ in project_scaffold.SCAFFOLD_FOLDERS]
    assert body["filesWritten"] == expected_paths
    assert len(calls) == 6
    assert [c["path"] for c in calls] == expected_paths
    assert all(c["owner"] == "mariana-org" and c["repo"] == "mini-me-demo" for c in calls)


def test_phase_artifact_commits_into_mapped_folder(client, monkeypatch):
    calls: list[dict] = []

    async def fake_create_or_update_file(self, auth_profile, owner, repo, path, content, message, branch):
        calls.append({"path": path, "content": content})

    from app.services.repositories.github_adapter import GitHubAdapter

    monkeypatch.setattr(GitHubAdapter, "create_or_update_file", fake_create_or_update_file)

    headers = {"Authorization": "Bearer test-api-key"}
    create = client.post("/projects", json={"name": "Proyecto Artifact"}, headers=headers)
    project_id = create.json()["id"]

    from app.core.storage import get_storage

    storage = get_storage()
    projects = storage.read_projects()
    project = next(p for p in projects if p["id"] == project_id)
    project["repositories"] = [
        {"id": "r1", "provider": "github", "owner": "o", "repo": "r", "defaultBranch": "main"}
    ]
    storage.write_projects(projects)

    response = client.post(
        f"/projects/{project_id}/phase-artifact",
        json={"phase": "backend", "filename": "hu-042.md", "content": "# HU-042"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["path"] == "03-Development/hu-042.md"
    assert calls == [{"path": "03-Development/hu-042.md", "content": "# HU-042"}]


def test_scaffold_without_repo_fails_cleanly(client):
    headers = {"Authorization": "Bearer test-api-key"}
    create = client.post(
        "/projects",
        json={"name": "Proyecto Sin Repo", "owner": "mariana"},
        headers=headers,
    )
    project_id = create.json()["id"]

    response = client.post(f"/projects/{project_id}/scaffold", headers=headers)
    assert response.status_code == 400
