"""
Repository adapter registry — ARCHITECTURE_JARVIS.md §1.2. Same pattern as
agent_registry.py: a router/service asks for an adapter by provider name and
never imports GitHubAdapter/BitbucketAdapter directly.
"""

from __future__ import annotations

from app.services.repositories.base import RepoAdapter
from app.services.repositories.bitbucket_adapter import BitbucketAdapter
from app.services.repositories.github_adapter import GitHubAdapter

_ADAPTERS: dict[str, RepoAdapter] = {
    "github": GitHubAdapter(),
    "bitbucket": BitbucketAdapter(),
}


def get_adapter(provider: str) -> RepoAdapter:
    try:
        return _ADAPTERS[provider]
    except KeyError as error:
        raise ValueError(f"Unknown repository provider: {provider!r}") from error


__all__ = ["RepoAdapter", "get_adapter"]
