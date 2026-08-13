"""
GitHub adapter — implements RepoAdapter (ARCHITECTURE_JARVIS.md §1.1, §1.2)
against the GitHub REST API v3 via httpx.AsyncClient.

# TODO: calibrar en implementacion — this parallel phase ("repositories") did
# not land a real adapter on disk (repositories/__init__.py already imported
# `GitHubAdapter`/`BitbucketAdapter` names that didn't exist yet). This is the
# integration agent's fill-in: a real, working implementation against the
# public REST APIs, not a stub, so /repositories and the jarvis_chat tools
# that eventually read repo data have something functional to call. Auth
# token resolution (auth_profile.token_ref -> actual header) is intentionally
# minimal — it reads an env var named by token_ref, which is exactly what
# Repository.accessTokenRef / AuthProfile.token_ref describe as the contract.
"""

from __future__ import annotations

import os
from datetime import datetime

import httpx

from app.schemas.auth_profile import AuthProfile
from app.schemas.repository import Commit, FileNode, PullRequest

_API_BASE = "https://api.github.com"


def _resolve_token(auth_profile: AuthProfile) -> str | None:
    # OAuth-created profiles (app/routers/oauth.py) carry the real token
    # directly — only the manual stand-in path resolves an env var by name.
    if auth_profile.auth_method == "oauth" and auth_profile.access_token:
        return auth_profile.access_token
    if not auth_profile.token_ref:
        return None
    return os.environ.get(auth_profile.token_ref)


def _headers(auth_profile: AuthProfile) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = _resolve_token(auth_profile)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class GitHubAdapter:
    async def validate_access(self, auth_profile: AuthProfile, owner: str, repo: str) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{_API_BASE}/repos/{owner}/{repo}", headers=_headers(auth_profile)
            )
        return response.status_code == 200

    async def list_commits_since(
        self, auth_profile: AuthProfile, owner: str, repo: str, since: datetime
    ) -> list[Commit]:
        params = {"since": since.isoformat()}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_API_BASE}/repos/{owner}/{repo}/commits",
                headers=_headers(auth_profile),
                params=params,
            )
        response.raise_for_status()
        commits: list[Commit] = []
        for item in response.json():
            commit_info = item.get("commit", {})
            author_info = commit_info.get("author", {})
            commits.append(
                Commit(
                    sha=item.get("sha", ""),
                    message=commit_info.get("message", ""),
                    author=author_info.get("name"),
                    date=author_info.get("date"),
                    url=item.get("html_url"),
                )
            )
        return commits

    async def list_pull_requests(
        self, auth_profile: AuthProfile, owner: str, repo: str, state: str = "open"
    ) -> list[PullRequest]:
        params = {"state": state}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_API_BASE}/repos/{owner}/{repo}/pulls",
                headers=_headers(auth_profile),
                params=params,
            )
        response.raise_for_status()
        pulls: list[PullRequest] = []
        for item in response.json():
            pulls.append(
                PullRequest(
                    id=item.get("number"),
                    title=item.get("title", ""),
                    state=item.get("state", state),
                    author=(item.get("user") or {}).get("login"),
                    createdAt=item.get("created_at"),
                    updatedAt=item.get("updated_at"),
                    mergedAt=item.get("merged_at"),
                    url=item.get("html_url"),
                )
            )
        return pulls

    async def get_file_tree(
        self, auth_profile: AuthProfile, owner: str, repo: str, branch: str
    ) -> list[FileNode]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}",
                headers=_headers(auth_profile),
                params={"recursive": "1"},
            )
        response.raise_for_status()
        tree = response.json().get("tree", [])
        return [
            FileNode(
                path=entry.get("path", ""),
                type="dir" if entry.get("type") == "tree" else "file",
                size=entry.get("size"),
            )
            for entry in tree
        ]

    async def get_file_content(
        self, auth_profile: AuthProfile, owner: str, repo: str, path: str, branch: str
    ) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_API_BASE}/repos/{owner}/{repo}/contents/{path}",
                headers=_headers(auth_profile),
                params={"ref": branch},
            )
        response.raise_for_status()
        payload = response.json()
        import base64

        content = payload.get("content", "")
        encoding = payload.get("encoding", "base64")
        if encoding == "base64":
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content
