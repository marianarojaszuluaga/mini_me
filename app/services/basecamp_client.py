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


async def list_basecamp_projects(auth_profile: AuthProfile, account_id: str) -> list[dict[str, Any]]:
    """Real projects of this Basecamp account — Tarea 2 Gap 3 (2026-08-21):
    lets the "Vincular Basecamp" modal show a real picker instead of asking
    for account_id/project_id typed by hand."""
    if not auth_profile.access_token:
        raise BasecampError("El Auth Profile de Basecamp no tiene un access_token real conectado.")

    headers = {"Authorization": f"Bearer {auth_profile.access_token}", "User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{_API_BASE}/{account_id}/projects.json", headers=headers)

    if response.status_code == 401:
        raise BasecampError("El token de Basecamp expiró o fue revocado — reconectá el Auth Profile.")
    response.raise_for_status()

    return [
        {"id": str(item.get("id")), "name": item.get("name", ""), "description": item.get("description")}
        for item in response.json()
    ]


async def list_card_tables(
    auth_profile: AuthProfile, account_id: str, project_id: str
) -> list[dict[str, Any]]:
    """Real Card Tables (Kanban boards: columnas + cards) of one Basecamp
    project. CORRECCIÓN 2026-08-21 (Mariana): la fuente real de "sprint
    actual" es la Card Table, nunca el todolist activo (get_active_sprint,
    arriba) — un proyecto puede tener más de una, así que se listan todas
    para que la usuaria elija una o varias, en vez de asumir "la primera"."""
    if not auth_profile.access_token:
        raise BasecampError("El Auth Profile de Basecamp no tiene un access_token real conectado.")

    headers = {"Authorization": f"Bearer {auth_profile.access_token}", "User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{_API_BASE}/{account_id}/buckets/{project_id}.json", headers=headers
        )

    if response.status_code == 401:
        raise BasecampError("El token de Basecamp expiró o fue revocado — reconectá el Auth Profile.")
    if response.status_code == 404:
        raise BasecampError("El proyecto de Basecamp vinculado no existe o no es accesible con este token.")
    response.raise_for_status()

    dock = response.json().get("dock", [])
    return [
        {"id": str(item.get("id")), "title": item.get("title") or "Card Table", "url": item.get("app_url")}
        for item in dock
        if item.get("name") == "kanban_board" and item.get("enabled")
    ]


async def get_card_table_snapshot(
    auth_profile: AuthProfile, account_id: str, project_id: str, card_table_id: str
) -> dict[str, Any]:
    """Real columns + cards of one Card Table — the actual "espejo" data
    (Tarea 2 Gap 3), never the todolist ratio. Returns
    {name, columns: [{name, cards: [{title, ...}]}]}."""
    if not auth_profile.access_token:
        raise BasecampError("El Auth Profile de Basecamp no tiene un access_token real conectado.")

    headers = {"Authorization": f"Bearer {auth_profile.access_token}", "User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=15.0) as client:
        table_response = await client.get(
            f"{_API_BASE}/{account_id}/buckets/{project_id}/card_tables/{card_table_id}.json",
            headers=headers,
        )
        if table_response.status_code == 401:
            raise BasecampError("El token de Basecamp expiró o fue revocado — reconectá el Auth Profile.")
        table_response.raise_for_status()
        table = table_response.json()

        columns: list[dict[str, Any]] = []
        for column in table.get("lists", []):
            cards_response = await client.get(
                f"{_API_BASE}/{account_id}/buckets/{project_id}/card_tables/lists/{column.get('id')}/cards.json",
                headers=headers,
            )
            cards_response.raise_for_status()
            columns.append(
                {
                    "name": column.get("title", ""),
                    "cards": [
                        {"title": card.get("title", ""), "dueOn": card.get("due_on"), "assignees": [
                            a.get("name") for a in card.get("assignees", [])
                        ]}
                        for card in cards_response.json()
                    ],
                }
            )

    return {"name": table.get("title") or "Card Table", "columns": columns}


async def resolve_message_board_id(
    auth_profile: AuthProfile, account_id: str, project_id: str
) -> str:
    """MessageBoardResolver (Basecamp Publisher, 2026-09-07) — SPEC
    §1.3/§1.7: lee el `dock` del proyecto real y extrae el item
    `message_board`. Se cachea en `Project.basecamp.message_board_id` por
    el llamador para no pegarle a esta API en cada publicación."""
    if not auth_profile.access_token:
        raise BasecampError("El Auth Profile de Basecamp no tiene un access_token real conectado.")

    headers = {"Authorization": f"Bearer {auth_profile.access_token}", "User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{_API_BASE}/{account_id}/buckets/{project_id}.json", headers=headers
        )
    if response.status_code == 401:
        raise BasecampError("El token de Basecamp expiró o fue revocado — reconectá el Auth Profile.")
    response.raise_for_status()

    dock = response.json().get("dock", [])
    board = next((item for item in dock if item.get("name") == "message_board"), None)
    if not board:
        # HU-041 E-4: el cliente deshabilitó el Message Board — falla
        # explícita e inmediata, nunca se inventa un id.
        raise BasecampError("Este proyecto de Basecamp no tiene Message Board habilitado.")
    return str(board["id"])


async def publish_message(
    auth_profile: AuthProfile,
    account_id: str,
    project_id: str,
    message_board_id: str,
    subject: str,
    content_html: str,
    category_id: int | None = None,
    notify_person_ids: list[int] | None = None,
) -> dict[str, Any]:
    """POST real a Basecamp Message Board (SPEC §1.3.B). `status: "active"`
    siempre — un post en draft no lo ve nadie (SPEC §1.3, nota real). Deja
    que el caller decida cómo mapear 401/429/4xx/5xx (BasecampPublisher —
    cada código tiene una acción distinta, ver SPEC §1.8/§2.3)."""
    if not auth_profile.access_token:
        raise BasecampError("El Auth Profile de Basecamp no tiene un access_token real conectado.")

    payload: dict[str, Any] = {"subject": subject, "content": content_html, "status": "active"}
    if category_id is not None:
        payload["category_id"] = category_id
    if notify_person_ids:
        payload["subscriptions"] = notify_person_ids

    headers = {
        "Authorization": f"Bearer {auth_profile.access_token}",
        "User-Agent": _USER_AGENT,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{_API_BASE}/{account_id}/buckets/{project_id}/message_boards/{message_board_id}/messages.json",
            headers=headers,
            json=payload,
        )
    return {"status_code": response.status_code, "body": _safe_json(response), "headers": dict(response.headers)}


async def list_categories(
    auth_profile: AuthProfile, account_id: str, project_id: str
) -> list[dict[str, Any]]:
    """Categorías reales del Message Board (HU-043 E-1) — valida un
    `category_id` recibido antes de guardarlo en la config de publicación,
    nunca confía en un id inventado por el frontend."""
    if not auth_profile.access_token:
        raise BasecampError("El Auth Profile de Basecamp no tiene un access_token real conectado.")

    headers = {"Authorization": f"Bearer {auth_profile.access_token}", "User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{_API_BASE}/{account_id}/buckets/{project_id}/categories.json", headers=headers
        )
    if response.status_code == 401:
        raise BasecampError("El token de Basecamp expiró o fue revocado — reconectá el Auth Profile.")
    response.raise_for_status()

    return [{"id": item.get("id"), "name": item.get("name", "")} for item in response.json()]


async def list_recent_messages(
    auth_profile: AuthProfile, account_id: str, project_id: str, message_board_id: str
) -> list[dict[str, Any]]:
    """Mensajes reales del Message Board (HU-046 E-3) — usado antes de
    reintentar un post fallido, para detectar si el POST anterior sí llegó
    a Basecamp pero el guardado local del id falló, y así evitar duplicar."""
    if not auth_profile.access_token:
        raise BasecampError("El Auth Profile de Basecamp no tiene un access_token real conectado.")

    headers = {"Authorization": f"Bearer {auth_profile.access_token}", "User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{_API_BASE}/{account_id}/buckets/{project_id}/message_boards/{message_board_id}/messages.json",
            headers=headers,
        )
    if response.status_code == 401:
        raise BasecampError("El token de Basecamp expiró o fue revocado — reconectá el Auth Profile.")
    response.raise_for_status()

    return [
        {"id": str(item.get("id")), "subject": item.get("subject", ""), "app_url": item.get("app_url")}
        for item in response.json()
    ]


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None
