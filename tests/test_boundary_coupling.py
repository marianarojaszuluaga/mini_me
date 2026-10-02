"""
Boundary test: Mini me's code must not grow new direct coupling to Basecamp
or ia-hybrid-teams beyond the handful of files that are explicitly the
integration boundary. This guards the "invoke, don't depend on" decision
from the 2026-09-22 coupling audit — it exists to catch a future ad-hoc
`import ia_hybrid_teams` or a hardcoded Basecamp call slipping in outside
the one client that owns that responsibility, not to police the word
"basecamp" appearing in comments/docs/schemas that just name the concept.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Files allowed to reference these systems directly — the actual integration
# boundary. Everything else under app/ and src/ (excluding tests/ and the
# bundled agent prompt .md files themselves, which are data, not code) must
# stay clean.
ALLOWED_FILES = {
    "app/services/basecamp_client.py",
    "app/services/basecamp_publisher.py",
    "app/services/agent_registry.py",
    "app/core/config.py",
    "app/schemas/auth_profile.py",  # Provider Literal — a domain enum value, not an import
    "app/schemas/project.py",  # BasecampLink/BasecampMirror — Mini me's own models
    "app/routers/oauth.py",  # generic OAuth router, references the provider name only
    "src/agents/registry.js",
    "app/phases/phase_contracts.py",  # provenance comment: "transcribed from ia-hybrid-teams/..."
    "src/phases/phaseContracts.js",  # same provenance comment, JS port
    "src/server.js",  # logs the resolved SPEC_KIT_AGENTS_DIR path at boot
}

SCAN_DIRS = ["app", "src"]
SCAN_SUFFIXES = {".py", ".js"}
FORBIDDEN_PATTERNS = [
    re.compile(r"\bia[-_]hybrid[-_]teams\b", re.IGNORECASE),
]
# "basecamp" is checked separately since so many *legitimate* domain files
# (schemas, basecamp_client.py, basecamp_publisher.py, basecamp_nomenclature.py
# — all Mini me's own code for its Autobasecamp feature) mention it by
# design. Only flag an import of an actual THIRD-PARTY basecamp package:
# `from app.services.basecamp_client import ...` or `require("./basecamp")`
# (internal, relative) must NOT match; `import basecamp` / `require("basecamp-sdk")`
# (a pip/npm package) must.
FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*(import|from)\s+basecamp\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"require\((['\"])(?!\.)[^'\"]*basecamp[^'\"]*\1\)", re.IGNORECASE),
]


def _relpath(p: Path) -> str:
    return p.relative_to(REPO_ROOT).as_posix()


def _iter_scanned_files():
    for scan_dir in SCAN_DIRS:
        base = REPO_ROOT / scan_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                continue
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            if "spec-kit-agents" in path.parts or "external-agents" in path.parts:
                continue  # bundled prompt data, not code
            yield path


def test_no_new_ia_hybrid_teams_filesystem_coupling():
    offenders = []
    for path in _iter_scanned_files():
        rel = _relpath(path)
        if rel in ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{rel}: matches {pattern.pattern!r}")

    assert not offenders, (
        "Found references to ia-hybrid-teams outside the allowed integration "
        "boundary (app/services/agent_registry.py, src/agents/registry.js, "
        "app/core/config.py). Route new agent-prompt loading through the "
        "existing SPEC_KIT_AGENTS_DIR/EXTERNAL_AGENTS_DIR mechanism instead:\n"
        + "\n".join(offenders)
    )


def test_no_new_basecamp_package_imports():
    offenders = []
    for path in _iter_scanned_files():
        rel = _relpath(path)
        if rel in ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in FORBIDDEN_IMPORT_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{rel}: matches {pattern.pattern!r}")

    assert not offenders, (
        "Found a direct import/require of a basecamp-named module outside "
        "app/services/basecamp_client.py. All Basecamp access should go "
        "through BasecampClient (HTTP only, no external basecamp package):\n"
        + "\n".join(offenders)
    )
