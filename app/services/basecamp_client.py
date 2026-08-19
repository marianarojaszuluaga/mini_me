"""
Basecamp client — real read against the bc-api (37signals) todolists
endpoint, used to surface a project's "sprint" (active to-do list) on the
Dashboard/detail views (Fase E, plan "UI 100% fiel al mockup").

Auth: reuses the Basecamp Auth Profile's OAuth access_token (same one
app/routers/oauth.py's Basecamp flow sets) — never a separate credential.
Real error, never fabricated success: a missing/expired token or an
unlinked/inaccessible Basecamp project raises, and the router surfaces that
as an explicit error to the frontend instead of a fake 200.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas.auth_profile import AuthProfile

_API_BASE = "https://3.basecampapi.com"
# 37signals' API requires a descriptive User-Agent identifying the app + a
# contact — an anonymous one is liable to be rate-limited/rejected.
_USER_AGENT = "Mar en internet (Orquestrador 360) (mariana.rojas@imagineapps.co)"


class BasecampError(RuntimeError):
    """Real, explicit failure talking to the Basecamp API — never swallowed
    into a fabricated empty/success response."""


def _parse_ratio(value: str | None) -> tuple[int, int]:
    if not value or "/" not in value:
        return (0, 0)
    done, total = value.split("/", 1)
    try:
        return (int(done), int(total))
    except ValueError:
        return (0, 0)


async def get_active_sprint(
    auth_profile: AuthProfile, account_id: str, project_id: str
) -> dict[str, Any]:
    """Returns the most recently active (non-fully-completed) to-do list for
    a linked Basecamp project, as {name, tasks_done, tasks_total}.

    Raises BasecampError on any real failure (no token, expired token, no
    access, no to-do lists at all) — the caller (router) turns that into an
    explicit HTTP error, not a fabricated empty sprint.
    """
    if not auth_profile.access_token:
        raise BasecampError("El Auth Profile de Basecamp no tiene un access_token real conectado.")

    headers = {
        "Authorization": f"Bearer {auth_profile.access_token}",
        "User-Agent": _USER_AGENT,
    }
    url = f"{_API_BASE}/{account_id}/buckets/{project_id}/todolists.json"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code == 401:
        raise BasecampError("El token de Basecamp expiró o fue revocado — reconectá el Auth Profile.")
    if response.status_code == 404:
        raise BasecampError("El proyecto de Basecamp vinculado no existe o no es accesible con este token.")
    response.raise_for_status()

    todolists = response.json()
    if not todolists:
        raise BasecampError("El proyecto de Basecamp vinculado no tiene to-do lists todavía.")

    active = [t for t in todolists if not t.get("completed")]
    pool = active or todolists
    pool.sort(key=lambda t: t.get("updated_at") or "", reverse=True)
    current = pool[0]

    tasks_done, tasks_total = _parse_ratio(current.get("completed_ratio"))
    return {
        "name": current.get("title") or current.get("name") or "Sprint actual",
        "tasks_done": tasks_done,
        "tasks_total": tasks_total,
    }
