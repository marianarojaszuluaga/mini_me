"""
System-improvement changelog (HU-009-JarvisMode, SPEC_JARVIS.md §10).

create_proposal() is meant to be called automatically by the HU-008
"2 consecutive low-quality invocations" detector once that's built (see the
TODO at the bottom of this file for where to wire it in). approve_proposal()
is the only thing that flips an entry from a passive proposal into a real
changelog entry — that's always Mar's explicit action, never automatic.
compute_after_scores() is meant to be called later (e.g. from a scheduled
job, alongside the sync cron in app/cron/) once after_window has elapsed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.storage import get_storage
from app.schemas.changelog import ChangelogEntry, DateWindow, DimensionScores
from app.services.metrics.collector import read_agent_evaluations


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _average_scores(agent_name: str, window: DateWindow) -> DimensionScores:
    """Averages the four HU-008 dimensions from metrics.collector's
    AgentEvaluation series for `agent_name` within `window`. Never invents a
    number: if no evaluations fall in the window, sample_count is 0 and the
    caller (compute_after_scores) is responsible for treating that as
    "not enough history yet" rather than a score."""
    rows = [
        row
        for row in read_agent_evaluations()
        if row.get("agent") == agent_name and window.start <= _parse_dt(row["date"]) <= window.end
    ]
    if not rows:
        return DimensionScores(eficiencia=0, acertividad=0, formato=0, calidad=0, sample_count=0)

    count = len(rows)
    return DimensionScores(
        eficiencia=sum(r["eficiencia"] for r in rows) / count,
        acertividad=sum(r["acertividad"] for r in rows) / count,
        formato=sum(r["formato"] for r in rows) / count,
        calidad=sum(r["calidad"] for r in rows) / count,
        sample_count=count,
    )


def list_entries() -> list[dict[str, Any]]:
    return get_storage().read_changelog()


def get_entry(entry_id: str) -> dict[str, Any] | None:
    return next((e for e in get_storage().read_changelog() if e.get("id") == entry_id), None)


def create_proposal(
    agent_name: str,
    what_changed: str,
    reason: str,
    before_window: DateWindow,
) -> dict[str, Any]:
    """Creates a pending changelog proposal — status "proposed", approved_at
    still None. before_scores is computed immediately from real history in
    before_window (never a placeholder); after_scores stays None until
    compute_after_scores() runs post-approval."""
    before_scores = _average_scores(agent_name, before_window)
    entry = ChangelogEntry(
        agent_name=agent_name,
        what_changed=what_changed,
        reason=reason,
        before_window=before_window,
        before_scores=before_scores,
        status="proposed",
    )
    storage = get_storage()
    entries = storage.read_changelog()
    entries.append(entry.model_dump(mode="json"))
    storage.write_changelog(entries)
    return entry.model_dump(mode="json")


def approve_proposal(entry_id: str) -> dict[str, Any] | None:
    """Marks a proposal as approved — this is Mar's explicit action
    (SPEC_JARVIS.md §10: 'nunca se autoaprueba'). Sets approved_at/applied_at
    to now and opens after_window as a same-length window starting now, so
    compute_after_scores() has a defined range to measure once time passes.
    Returns None if entry_id doesn't exist."""
    storage = get_storage()
    entries = storage.read_changelog()
    target = next((e for e in entries if e.get("id") == entry_id), None)
    if target is None:
        return None

    now = datetime.now(timezone.utc)
    before_window = target["before_window"]
    window_length = _parse_dt(before_window["end"]) - _parse_dt(before_window["start"])

    now_iso = now.isoformat().replace("+00:00", "Z")
    target["approved_at"] = now_iso
    target["applied_at"] = now_iso
    target["after_window"] = {
        "start": now_iso,
        "end": (now + window_length).isoformat().replace("+00:00", "Z"),
    }
    target["status"] = "approved"

    storage.write_changelog(entries)
    return target


def compute_after_scores(entry_id: str) -> dict[str, Any] | None:
    """Aggregates real AgentEvaluation scores from after_window and fills in
    after_scores. Call this once after_window.end has passed (or repeatedly
    to refresh a partial in-progress read) — never invents a projected
    number. If after_window isn't set (not approved yet) or there still
    isn't enough history, after_scores/sample_count stay at 0 and the
    caller/API renders that as "en progreso" per SPEC_JARVIS.md §10.
    Returns None if entry_id doesn't exist."""
    storage = get_storage()
    entries = storage.read_changelog()
    target = next((e for e in entries if e.get("id") == entry_id), None)
    if target is None:
        return None

    after_window = target.get("after_window")
    if after_window is None:
        # Not approved yet — nothing to measure.
        return target

    window = DateWindow(start=after_window["start"], end=after_window["end"])
    scores = _average_scores(target["agent_name"], window)
    target["after_scores"] = scores.model_dump(mode="json")
    if scores.sample_count > 0:
        target["status"] = "measured"

    storage.write_changelog(entries)
    return target


# HU-008-JarvisMode integration point ----------------------------------------
# The "2 invocaciones seguidas bajas" detector (SPEC_JARVIS.md §8: reads
# metrics.collector.read_agent_evaluations(), checks the last two consecutive
# records per agent per dimension against the threshold) is being built in a
# parallel task and does not exist in this codebase yet. Once it lands, it
# should call `create_proposal(agent_name, what_changed, reason,
# before_window)` from wherever it detects the two-low-in-a-row pattern —
# the proposal always starts as "proposed"; approval stays Mar's explicit
# action via approve_proposal(), never automatic.
