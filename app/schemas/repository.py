"""
Value objects returned by RepoAdapter implementations (ARCHITECTURE_JARVIS.md
§1.1). Not persisted as-is — the digest/reconciliation services read these
and fold the relevant bits into project.memory.projectBrain.

# TODO: calibrar en implementacion — el shape final de estos objetos puede
# crecer (p.ej. Commit.stats) una vez que el digest historico (§Flujo A.4)
# y la reconciliacion (SPEC_JARVIS.md §6.7) esten implementados y se sepa
# exactamente que campos consumen.
"""

from __future__ import annotations

from pydantic import BaseModel


class Commit(BaseModel):
    sha: str
    message: str
    author: str | None = None
    date: str | None = None
    url: str | None = None


class PullRequest(BaseModel):
    id: int | str
    title: str
    state: str
    author: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
    mergedAt: str | None = None
    url: str | None = None


class FileNode(BaseModel):
    path: str
    type: str  # "file" | "dir"
    size: int | None = None


class RepoSummary(BaseModel):
    """One repo from the connected account's real list — Tarea 2 Gap 2
    (2026-08-21): 'jalar (pull) los repos que existen en la cuenta' instead
    of typing owner/repo by hand. Extra metadata (description/language/
    default branch) becomes real project context, not just an identifier."""

    owner: str
    repo: str
    description: str | None = None
    language: str | None = None
    defaultBranch: str = "main"
    private: bool = False
    url: str | None = None
