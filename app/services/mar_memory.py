"""
CRUD for the Memoria de Mar (SPEC_JARVIS.md §6.3, HU-007-JarvisMode).

Deduplication rule (own decision, spec leaves the exact heuristic as an
implementation detail): a new entry is treated as "essentially the same
idea" as an existing one when they share the same `type` AND their content
passes a simple token-overlap similarity check (Jaccard over lowercased
word sets) above a threshold. In that case we update the existing entry's
content/source/createdAt in place instead of appending a duplicate. This
keeps the "glosario vivo" from accumulating near-identical entries every
time the chat re-derives the same understanding across turns.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.storage import get_storage
from app.schemas.mar_memory import MarMemoryEntry

# TODO: calibrar en implementacion — 0.6 is a starting point; tune once real
# chat-derived entries are observed.
_SIMILARITY_THRESHOLD = 0.6

_WORD_RE = re.compile(r"[a-záéíóúñü0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _similarity(a: str, b: str) -> float:
    tokens_a, tokens_b = _tokenize(a), _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def get_all_entries() -> list[dict[str, Any]]:
    return get_storage().read_mar_memory()


def _find_similar_entry(
    entries: list[dict[str, Any]], entry_type: str, content: str
) -> dict[str, Any] | None:
    for existing in entries:
        if existing.get("type") != entry_type:
            continue
        if _similarity(existing.get("content", ""), content) >= _SIMILARITY_THRESHOLD:
            return existing
    return None


def add_or_update_entry(entry: MarMemoryEntry) -> dict[str, Any]:
    """Adds `entry` as a new Memoria de Mar entry, unless an existing entry
    of the same type is similar enough to the new content — in which case
    that existing entry is updated in place (content/source/createdAt
    refreshed, id preserved) and returned instead.

    If `entry.id` matches an existing entry's id, that's treated as an
    explicit update request regardless of similarity.
    """
    storage = get_storage()
    entries = storage.read_mar_memory()

    existing_by_id = next((e for e in entries if e.get("id") == entry.id), None)
    target = existing_by_id or _find_similar_entry(entries, entry.type, entry.content)

    if target is not None:
        target["type"] = entry.type
        target["content"] = entry.content
        target["source"] = entry.source
        target["createdAt"] = entry.createdAt
        storage.write_mar_memory(entries)
        return target

    new_entry = entry.model_dump()
    entries.append(new_entry)
    storage.write_mar_memory(entries)
    return new_entry


def delete_entry(entry_id: str) -> bool:
    storage = get_storage()
    entries = storage.read_mar_memory()
    remaining = [e for e in entries if e.get("id") != entry_id]
    if len(remaining) == len(entries):
        return False
    storage.write_mar_memory(remaining)
    return True
