"""
Bitbucket adapter — implements RepoAdapter (ARCHITECTURE_JARVIS.md §1.1, §1.2)
against the Bitbucket Cloud REST API 2.0 via httpx.AsyncClient.

# TODO: calibrar en implementacion — same fill-in situation as
# github_adapter.py: the parallel "repositories" phase left the registry
# referencing this class without an implementation on disk. This is a real,
# working implementation against Bitbucket Cloud's public API, not a stub.
"""

from __future__ import annotations

import os
from datetime import datetime

import httpx

from app.schemas.auth_profile import AuthProfile
from app.schemas.repository import Commit, FileNode, PullRequest

_API_BASE = "https://api.bitbucket.org/2.0"


def _resolve_token(auth_profile: AuthProfile) -> str | None:
    if not auth_profile.token_ref:
        return None
    return os.environ.get(auth_profile.token_ref)


def _headers(auth_profile: AuthProfile) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = _resolve_token(auth_profile)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class BitbucketAdapter:
    async def validate_access(self, auth_profile: AuthProfile, owner: str, repo: str) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{_API_BASE}/repositories/{owner}/{repo}", headers=_headers(auth_profile)
            )
        return response.status_code == 200

    async def list_commits_since(
        self, auth_profile: AuthProfile, owner: str, repo: str, since: datetime
    ) -> list[Commit]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_API_BASE}/repositories/{owner}/{repo}/commits",
                headers=_headers(auth_profile),
            )
        response.raise_for_status()
        commits: list[Commit] = []
        for item in response.json().get("values", []):
            date_str = item.get("date")
            if date_str:
                try:
                    parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if since.tzinfo is not None and parsed < since:
                        continue
                except ValueError:
                    pass
            commits.append(
                Commit(
                    sha=item.get("hash", ""),
                    message=item.get("message", ""),
                    author=(item.get("author") or {}).get("raw"),
                    date=date_str,
                    url=(item.get("links") or {}).get("html", {}).get("href"),
                )
            )
        return commits

    async def list_pull_requests(
        self, auth_profile: AuthProfile, owner: str, repo: str, state: str = "OPEN"
    ) -> list[PullRequest]:
        params = {"state": state.upper()}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_API_BASE}/repositories/{owner}/{repo}/pullrequests",
                headers=_headers(auth_profile),
                params=params,
            )
        response.raise_for_status()
        pulls: list[PullRequest] = []
        for item in response.json().get("values", []):
            pulls.append(
                PullRequest(
                    id=item.get("id"),
                    title=item.get("title", ""),
                    state=item.get("state", state),
                    author=(item.get("author") or {}).get("display_name"),
                    createdAt=item.get("created_on"),
                    updatedAt=item.get("updated_on"),
                    mergedAt=None,
                    url=(item.get("links") or {}).get("html", {}).get("href"),
                )
            )
        return pulls

    async def get_file_tree(
        self, auth_profile: AuthProfile, owner: str, repo: str, branch: str
    ) -> list[FileNode]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_API_BASE}/repositories/{owner}/{repo}/src/{branch}/",
                headers=_headers(auth_profile),
                params={"max_depth": 100},
            )
        response.raise_for_status()
        entries = response.json().get("values", [])
        return [
            FileNode(
                path=entry.get("path", ""),
                type="dir" if entry.get("type") == "commit_directory" else "file",
                size=entry.get("size"),
            )
            for entry in entries
        ]

    async def get_file_content(
        self, auth_profile: AuthProfile, owner: str, repo: str, path: str, branch: str
    ) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_API_BASE}/repositories/{owner}/{repo}/src/{branch}/{path}",
                headers=_headers(auth_profile),
            )
        response.raise_for_status()
        return response.text
