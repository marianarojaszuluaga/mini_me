"""
Basecamp Message Board Publisher — dominio real (2026-09-07).

Adaptado de SPEC-basecamp-message-board-publisher.md + HU-041 a HU-046 +
PLAN-GABI-basecamp-publisher.md, construido dentro de orquestrador-360 (no
como proyecto "Scrum Assistant" aparte — ese código no existe todavía; esta
build reusa la infraestructura real ya existente acá: OAuth real
(app/routers/oauth.py), cliente HTTP de Basecamp (basecamp_client.py) y el
modelo de proyecto con vínculo a Basecamp (BasecampLink)).

Responsabilidad única por función/clase (SOLID §S del plan de Gabi):
- `render_sprint_started` / `render_sprint_closed` — PostRenderer (puro, sin red).
- `_sanitize_html` — sanitizador con lista blanca (tarea 44 del plan).
- `resolve_and_cache_board_id` — wrapper de MessageBoardResolver que cachea en Project.
- `publish_event` — BasecampPublisher.publish(event): idempotencia + POST + persistencia.

NO implementado todavía (fuera de esta pasada, ver qa/... y el reporte a Mariana):
- `PublicationQueue` con reintentos/backoff asíncronos (Fase 2, tarea 45) — hoy `publish_event`
  es síncrono; HU-041 CA-6 ("no espera a Basecamp") queda pendiente de una cola real.
- `OrphanSweeper` (tarea 45b).
- Los 4 endpoints de Fase 3 y los 4 componentes de Fase 4.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

from app.core.storage import get_storage
from app.schemas.basecamp_publication import (
    BasecampPublication,
    EventType,
    SprintClosedPayload,
    SprintStartedPayload,
)
from app.schemas.auth_profile import AuthProfile
from app.services.basecamp_client import (
    BasecampError,
    list_recent_messages,
    publish_message,
    resolve_message_board_id,
)

_PUBLICATIONS_SERIES = "basecamp-publications"

# HU-045 CA-3 backoff — indexado por `attempts`, tope en el último valor para
# no crecer sin límite (2s/8s/32s/2m/8m).
_BACKOFF_SECONDS = [2, 8, 32, 120, 480]

# SPEC §1.5 — tags permitidos en el Message Board (Chatbot-only tags como
# <table>/<details>/<summary> quedan fuera a propósito, R-4 del plan).
_ALLOWED_TAGS = {"div", "br", "strong", "em", "strike", "a", "pre", "blockquote", "ul", "ol", "li", "h1", "bc-attachment"}
_ALLOWED_ATTRS = {"a": {"href"}, "bc-attachment": {"sgid"}}


class _Sanitizer(HTMLParser):
    """Sanitizador con lista blanca real (SPEC §1.5, plan tarea 44) — tags
    no permitidos se eliminan mantenienddo su texto interno; nunca se
    escapa a ciegas todo el HTML (los templates SÍ necesitan <strong>/<ul>
    reales)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _ALLOWED_TAGS:
            return
        allowed_attrs = _ALLOWED_ATTRS.get(tag, set())
        kept = [f'{name}="{value}"' for name, value in attrs if name in allowed_attrs and value]
        self._out.append(f"<{tag}{' ' + ' '.join(kept) if kept else ''}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _ALLOWED_TAGS:
            self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self._out.append(data)

    def get_html(self) -> str:
        return "".join(self._out)


def _sanitize_html(raw_html: str) -> str:
    sanitizer = _Sanitizer()
    sanitizer.feed(raw_html)
    return sanitizer.get_html()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_sprint_started(payload: SprintStartedPayload) -> tuple[str, str]:
    """PostRenderer — plantilla de inicio (SPEC §2.4). Puro: sin red, sin
    base de datos — la pieza que el plan de Gabi pide testear primero
    (§6.5). E-5: si `scope` está vacío, la sección se omite (nunca una
    lista vacía)."""
    subject = f"{payload.sprint_name} — Inicio ({payload.period['start']} – {payload.period['end']})"

    parts = [f"<div><strong>Objetivo:</strong> {_escape(payload.goal or '(sin objetivo definido)')}</div>"]
    parts.append(f"<div><strong>Periodo:</strong> {payload.period['start']} – {payload.period['end']}</div>")
    parts.append(f"<div><strong>Comprometido:</strong> {payload.committed} tarjetas</div>")

    if payload.scope:
        parts.append("<h1>Alcance</h1><ul>")
        for item in payload.scope:
            owner_suffix = f" — {_escape(item['owner'])}" if item.get("owner") else ""
            parts.append(f"<li><a href=\"{item.get('url', '')}\">{_escape(item.get('title', ''))}</a>{owner_suffix}</li>")
        parts.append("</ul>")

    parts.append("<div><em>Publicado automáticamente por Minime</em></div>")
    return subject, _sanitize_html("".join(parts))


def render_sprint_closed(payload: SprintClosedPayload) -> tuple[str, str]:
    """PostRenderer — plantilla de cierre (SPEC §2.5). E-4: 0 completados
    se publica igual, sin tratarlo como error. E-5 (carry-over vacío): la
    sección se omite por completo, nunca un encabezado con lista vacía."""
    subject = f"{payload.sprint_name} — Cierre ({payload.completed}/{payload.committed} completados)"

    cumplido = " — cumplido" if payload.completed >= payload.committed else ""
    parts = [f"<div><strong>Completado:</strong> {payload.completed} de {payload.committed} comprometidos</div>"]
    parts.append(f"<div><strong>Objetivo:</strong> {_escape(payload.goal or '(sin objetivo definido)')}{cumplido}</div>")

    if payload.carry_over:
        parts.append("<h1>Carry-over al próximo sprint</h1><ul>")
        for item in payload.carry_over:
            parts.append(f"<li><a href=\"{item.get('url', '')}\">{_escape(item.get('title', ''))}</a></li>")
        parts.append("</ul>")

    parts.append("<div><em>Publicado automáticamente por Minime</em></div>")
    return subject, _sanitize_html("".join(parts))


def _find_publication(sprint_id: str, event_type: EventType) -> dict[str, Any] | None:
    """Idempotencia real (HU-046) — reemplaza el `UNIQUE (sprint_id,
    event_type)` de SQL del spec original: buscamos antes de insertar,
    en vez de confiar en un constraint de base de datos que Redis/JSON no
    tiene."""
    storage = get_storage()
    for row in storage.read_series(_PUBLICATIONS_SERIES):
        if row.get("sprint_id") == sprint_id and row.get("event_type") == event_type:
            return row
    return None


async def resolve_and_cache_board_id(
    auth_profile: AuthProfile, account_id: str, bucket_id: str, project: dict[str, Any]
) -> str:
    """Cachea `message_board_id` en `project["basecamp"]` (SPEC §1.7) para
    no repetir el GET en cada publicación."""
    cached = (project.get("basecamp") or {}).get("message_board_id")
    if cached:
        return cached

    board_id = await resolve_message_board_id(auth_profile, account_id, bucket_id)
    project.setdefault("basecamp", {})["message_board_id"] = board_id
    storage = get_storage()
    projects = storage.read_projects()
    for p in projects:
        if p.get("id") == project.get("id"):
            p.setdefault("basecamp", {})["message_board_id"] = board_id
    storage.write_projects(projects)
    return board_id


async def publish_event(
    auth_profile: AuthProfile,
    project: dict[str, Any],
    sprint_id: str,
    event_type: EventType,
    payload: SprintStartedPayload | SprintClosedPayload,
) -> BasecampPublication:
    """BasecampPublisher.publish(event) — SPEC §2.1/§2.2/§2.3. Síncrono por
    ahora (ver docstring del módulo — la cola real, tarea 45, no está
    construida todavía): quien llame a esto debe saber que sí espera a
    Basecamp, a diferencia de HU-041 CA-6."""
    existing = _find_publication(sprint_id, event_type)
    if existing:
        return BasecampPublication(**existing)

    basecamp = project.get("basecamp") or {}
    if not basecamp:
        raise BasecampError("Este proyecto no tiene un proyecto de Basecamp vinculado.")

    account_id = str(basecamp["account_id"])
    bucket_id = str(basecamp["project_id"])
    config = basecamp.get("publish") or {}
    if not config.get("enabled"):
        raise BasecampError("La publicación en Basecamp está desactivada para este proyecto (HU-043).")
    if event_type == "sprint.started" and not config.get("publish_on_start", True):
        raise BasecampError("Este proyecto tiene publish_on_start desactivado.")
    if event_type == "sprint.closed" and not config.get("publish_on_close", True):
        raise BasecampError("Este proyecto tiene publish_on_close desactivado.")

    message_board_id = await resolve_and_cache_board_id(auth_profile, account_id, bucket_id, project)

    if event_type == "sprint.started":
        subject, content_html = render_sprint_started(payload)  # type: ignore[arg-type]
    else:
        subject, content_html = render_sprint_closed(payload)  # type: ignore[arg-type]

    publication = BasecampPublication(
        sprint_id=sprint_id,
        project_id=project["id"],
        event_type=event_type,
        bucket_id=bucket_id,
        message_board_id=message_board_id,
    )

    result = await publish_message(
        auth_profile,
        account_id,
        bucket_id,
        message_board_id,
        subject,
        content_html,
        category_id=config.get("category_id"),
        notify_person_ids=config.get("notify_person_ids"),
    )

    _apply_publish_result(publication, result)
    if publication.status == "pending" and 500 <= result["status_code"] < 600:
        publication.attempts = 1

    storage = get_storage()
    storage.append_series(_PUBLICATIONS_SERIES, publication.model_dump(mode="json"))
    return publication


def _apply_publish_result(publication: BasecampPublication, result: dict[str, Any]) -> None:
    """SPEC §2.3 — mapeo real de códigos, no genérico. Compartido entre
    `publish_event` (primer intento) y `retry_publication` (reintentos) para
    no duplicar el mapeo de status codes."""
    status_code = result["status_code"]
    if status_code == 201:
        publication.status = "sent"
        publication.basecamp_message_id = str(result["body"].get("id"))
        publication.basecamp_url = result["body"].get("app_url")
        from datetime import datetime, timezone

        publication.sent_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    elif status_code == 401:
        publication.status = "failed"
        publication.last_error = "Sesión de Basecamp expirada, reconecta la cuenta"
    elif status_code == 429:
        publication.status = "pending"
        publication.last_error = f"Rate limit — Retry-After: {result['headers'].get('Retry-After', '?')}"
    elif 500 <= status_code < 600:
        publication.status = "pending"
        publication.last_error = f"Basecamp respondió {status_code}"
    else:
        publication.status = "failed"
        publication.last_error = f"Basecamp rechazó el payload ({status_code}): {result['body']}"


def _backoff_elapsed(publication: BasecampPublication) -> bool:
    """HU-045 CA-3 — no hay un campo `last_attempt_at` separado (mantenemos
    el modelo simple, tarea 45), así que el backoff se mide desde
    `created_at`: aproximación razonable porque cada intento fallido no
    mueve `created_at`, y en la práctica el primer y único intento previo
    ya ocurrió muy cerca de `created_at` (publish_event es síncrono)."""
    from datetime import datetime

    index = min(publication.attempts, len(_BACKOFF_SECONDS) - 1)
    wait_seconds = _BACKOFF_SECONDS[index]
    created = datetime.fromisoformat(publication.created_at.replace("Z", "+00:00"))
    now = datetime.now(created.tzinfo)
    return (now - created).total_seconds() >= wait_seconds


def _rewrite_publication(publication: BasecampPublication) -> None:
    """No hay update-by-id en storage.py (solo append_series/write_series) —
    reescribe la serie completa reemplazando la fila con el mismo id."""
    storage = get_storage()
    rows = storage.read_series(_PUBLICATIONS_SERIES)
    updated = publication.model_dump(mode="json")
    rows = [updated if row.get("id") == publication.id else row for row in rows]
    storage.write_series(_PUBLICATIONS_SERIES, rows)


async def retry_publication(
    publication_id: str,
    auth_profile: AuthProfile | None = None,
    project: dict[str, Any] | None = None,
    payload: SprintStartedPayload | SprintClosedPayload | None = None,
) -> BasecampPublication:
    """HU-045 — reintenta una publicación `pending`/`failed` con los datos
    ACTUALES del sprint (CA-3), respetando el backoff 2s/8s/32s/2m/8m.

    Si ya está `sent` o no existe, es un no-op (idempotente, HU-045 CA-6):
    devuelve la publicación tal cual (o levanta si no existe — nada que
    reintentar sin saber qué publicación es). `auth_profile`/`project`/
    `payload` son opcionales para permitir la lectura pura del estado (p.
    ej. el endpoint GET .../publications antes de que el backoff elapse);
    son requeridos quien SÍ quiere reintentar de verdad."""
    storage = get_storage()
    rows = storage.read_series(_PUBLICATIONS_SERIES)
    row = next((r for r in rows if r.get("id") == publication_id), None)
    if row is None:
        raise BasecampError(f"No existe una publicación con id {publication_id}.")

    publication = BasecampPublication(**row)
    if publication.status == "sent":
        return publication  # HU-045 CA-6 — idempotente, nunca duplica
    if publication.status not in ("pending", "failed"):
        return publication

    if not _backoff_elapsed(publication):
        return publication  # todavía no toca reintentar

    if auth_profile is None or project is None or payload is None:
        # Sin contexto real para reintentar (solo se pidió el estado) — se
        # devuelve sin tocar, el próximo caller con contexto completo hace
        # el reintento real.
        return publication

    basecamp = project.get("basecamp") or {}
    account_id = str(basecamp["account_id"])
    bucket_id = str(basecamp["project_id"])
    config = basecamp.get("publish") or {}

    if publication.event_type == "sprint.started":
        subject, content_html = render_sprint_started(payload)  # type: ignore[arg-type]
    else:
        subject, content_html = render_sprint_closed(payload)  # type: ignore[arg-type]

    # HU-046 E-3 — antes de reintentar, chequear si el POST anterior en
    # realidad sí llegó (y solo falló guardar el resultado): busca un mensaje
    # existente con el mismo subject exacto para no duplicar.
    try:
        recent = await list_recent_messages(auth_profile, account_id, bucket_id, publication.message_board_id)
    except BasecampError:
        recent = []
    found = next((m for m in recent if m.get("subject") == subject), None)
    if found:
        publication.status = "sent"
        publication.basecamp_message_id = str(found.get("id"))
        publication.basecamp_url = found.get("app_url")
        from datetime import datetime, timezone

        publication.sent_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _rewrite_publication(publication)
        return publication

    publication.attempts += 1
    result = await publish_message(
        auth_profile,
        account_id,
        bucket_id,
        publication.message_board_id,
        subject,
        content_html,
        category_id=config.get("category_id"),
        notify_person_ids=config.get("notify_person_ids"),
    )
    _apply_publish_result(publication, result)
    _rewrite_publication(publication)
    return publication


async def sweep_orphans(auth_profile_lookup: Any) -> list[BasecampPublication]:
    """HU-046 E-2 — barre publicaciones `pending` con más de 15 minutos
    desde `created_at` y las reintenta (reusa `retry_publication`).

    No hay worker/cron real en este stack (Vercel serverless, ver plan §1.1
    Opción A) — esto se llama de forma perezosa desde un endpoint (p. ej. el
    GET .../publications de Fase 3), nunca desde un scheduler propio.

    `auth_profile_lookup(project_id: str) -> tuple[AuthProfile, dict] | None`
    — cada publicación necesita el Auth Profile + project reales de SU
    project_id, no uno global, así que se recibe un callback en vez de
    hardcodear cómo se resuelve (el caller decide: leer storage, cachear,
    etc.) — mantiene esta función simple y testeable con un fake."""
    from datetime import datetime

    storage = get_storage()
    rows = storage.read_series(_PUBLICATIONS_SERIES)
    touched: list[BasecampPublication] = []

    for row in rows:
        if row.get("status") != "pending":
            continue
        created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        now = datetime.now(created.tzinfo)
        if (now - created).total_seconds() < 15 * 60:
            continue

        lookup = auth_profile_lookup(row["project_id"])
        if lookup is None:
            continue
        auth_profile, project = lookup
        payload = _rebuild_payload(row, project)
        if payload is None:
            continue
        touched.append(await retry_publication(row["id"], auth_profile, project, payload))

    return touched


def _rebuild_payload(
    row: dict[str, Any], project: dict[str, Any]
) -> SprintStartedPayload | SprintClosedPayload | None:
    """`sweep_orphans` no recibe un payload por publicación (barre muchas a
    la vez) — reconstruye uno mínimo desde `Project.memory.sprints` (§4a: no
    hay dominio de Sprint propio) para poder re-renderizar con datos
    razonablemente actuales. Si el proyecto no tiene memoria de sprint
    todavía, no hay con qué reintentar de verdad."""
    sprints = (project.get("memory") or {}).get("sprints")
    if not sprints:
        return None
    name = f"Sprint {sprints.get('current', '?')}"
    period = {"start": "", "end": ""}
    if row["event_type"] == "sprint.started":
        return SprintStartedPayload(sprint_name=name, period=period, committed=0)
    return SprintClosedPayload(sprint_name=name, period=period, committed=0, completed=0)
