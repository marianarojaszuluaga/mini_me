"""
Verifies every bundled agent prompt .md file under src/agents/spec-kit-agents/
and src/agents/external-agents/ matches the hash recorded in
src/agents/agents.lock.json. This is the pytest-side half of the sync gap
closed by scripts/sync-agents.js --check: if this fails, someone edited a
prompt file locally without running `npm run sync-agents`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = REPO_ROOT / "src" / "agents" / "agents.lock.json"

GROUPS = {
    "spec-kit-agents": REPO_ROOT / "src" / "agents" / "spec-kit-agents",
    "external-agents": REPO_ROOT / "src" / "agents" / "external-agents",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lockfile_exists():
    assert LOCK_PATH.exists(), (
        "src/agents/agents.lock.json is missing — run `npm run sync-agents` "
        "to generate it."
    )


def test_bundled_agent_prompts_match_lockfile():
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    problems = []

    for group_key, bundled_dir in GROUPS.items():
        lock_entries = lock.get("agents", {}).get(group_key, {})
        on_disk = {p.name for p in bundled_dir.glob("*.md")} if bundled_dir.exists() else set()

        for filename in on_disk:
            recorded = lock_entries.get(filename)
            if not recorded:
                problems.append(f"[{group_key}] {filename}: no lock entry")
                continue
            actual_hash = _sha256(bundled_dir / filename)
            if recorded["sha256"] != actual_hash:
                problems.append(f"[{group_key}] {filename}: hash mismatch")

        for filename in lock_entries:
            if filename not in on_disk:
                problems.append(f"[{group_key}] {filename}: in lock but missing on disk")

    assert not problems, (
        "Agent prompt files out of sync with agents.lock.json — run "
        "`npm run sync-agents` and commit the result:\n"
        + "\n".join(problems)
    )
