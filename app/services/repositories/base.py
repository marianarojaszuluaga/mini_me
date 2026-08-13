"""
Common interface for repository adapters — ARCHITECTURE_JARVIS.md §1.1.

A Protocol (not an ABC) on purpose: GitHubAdapter/BitbucketAdapter don't need
to inherit from anything, they just need to satisfy this shape structurally.
Consumers (digest, reconciliation, chat tools) type-hint against this and
never import a concrete adapter directly — see repositories/__init__.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.schemas.auth_profile import AuthProfile
from app.schemas.repository import Commit, FileNode, PullRequest


class RepoAdapter(Protocol):
    async def validate_access(
        self, auth_profile: AuthProfile, owner: str, repo: str
    ) -> bool: ...

    async def list_commits_since(
        self, auth_profile: AuthProfile, owner: str, repo: str, since: datetime
    ) -> list[Commit]: ...

    async def list_pull_requests(
        self, auth_profile: AuthProfile, owner: str, repo: str, state: str
    ) -> list[PullRequest]: ...

    async def get_file_tree(
        self, auth_profile: AuthProfile, owner: str, repo: str, branch: str
    ) -> list[FileNode]: ...

    async def get_file_content(
        self, auth_profile: AuthProfile, owner: str, repo: str, path: str, branch: str
    ) -> str: ...
