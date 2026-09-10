"""
Unit tests for the Basecamp Message Board Publisher's PostRenderer —
plan de Gabi §6.1/§6.5: "escribir primero los tests del PostRenderer, es la
pieza pura donde vive la mayoría de los bugs de formato". Sin red, sin
storage — solo las funciones puras de app/services/basecamp_publisher.py.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app.schemas.auth_profile import AuthProfile
from app.schemas.basecamp_publication import BasecampPublication, SprintClosedPayload, SprintStartedPayload
from app.services import basecamp_publisher
from app.services.basecamp_publisher import (
    _sanitize_html,
    render_sprint_closed,
    render_sprint_started,
    retry_publication,
    sweep_orphans,
)


def test_inicio_con_alcance():
    payload = SprintStartedPayload(
        sprint_name="Sprint 12",
        goal="Cerrar flujo de autenticación",
        period={"start": "2026-08-19", "end": "2026-09-02"},
        committed=2,
        scope=[{"title": "Login OAuth", "url": "https://x", "owner": "Daniel"}],
    )
    subject, html = render_sprint_started(payload)
    assert subject == "Sprint 12 — Inicio (2026-08-19 – 2026-09-02)"
    assert "<h1>Alcance</h1>" in html
    assert "Login OAuth" in html
    assert "Daniel" in html


def test_inicio_sin_tarjetas_omite_seccion():
    payload = SprintStartedPayload(
        sprint_name="Sprint 13", period={"start": "a", "end": "b"}, committed=0, scope=[]
    )
    _, html = render_sprint_started(payload)
    assert "<h1>Alcance</h1>" not in html


def test_cierre_con_carry_over():
    payload = SprintClosedPayload(
        sprint_name="Sprint 12",
        goal="Cerrar flujo de autenticación",
        period={"start": "a", "end": "b"},
        committed=10,
        completed=8,
        carry_over=[{"title": "Refactor de tokens", "url": "https://x"}],
    )
    subject, html = render_sprint_closed(payload)
    assert subject == "Sprint 12 — Cierre (8/10 completados)"
    assert "Carry-over al próximo sprint" in html
    assert "Refactor de tokens" in html
    assert "cumplido" not in html  # 8 < 10, no se marca cumplido


def test_cierre_sin_carry_over_omite_seccion():
    payload = SprintClosedPayload(
        sprint_name="Sprint 12", period={"start": "a", "end": "b"}, committed=10, completed=10, carry_over=[]
    )
    _, html = render_sprint_closed(payload)
    assert "Carry-over" not in html
    assert "cumplido" in html  # 10 >= 10


def test_cierre_cero_completados():
    payload = SprintClosedPayload(
        sprint_name="Sprint 14",
        period={"start": "a", "end": "b"},
        committed=5,
        completed=0,
        carry_over=[{"title": "x", "url": "y"}],
    )
    subject, html = render_sprint_closed(payload)
    assert subject == "Sprint 14 — Cierre (0/5 completados)"
    assert "0 de 5" in html


def test_sanitizador_elimina_table_pero_conserva_texto():
    dirty = "<div>ok</div><table><tr><td>bad</td></tr></table>"
    clean = _sanitize_html(dirty)
    assert "<table>" not in clean
    assert "<tr>" not in clean
    assert "<td>" not in clean
    assert "bad" in clean  # texto interno se conserva, solo se quita el tag


def test_sanitizador_conserva_tags_permitidos():
    allowed = "<div><strong>bold</strong> <a href=\"https://x\">link</a></div>"
    clean = _sanitize_html(allowed)
    assert clean == allowed


# ---------------------------------------------------------------------------
# retry_publication / sweep_orphans (Fase 2 resto, plan §1.2) — sin red real:
# FakeStorage en memoria + publish_message/list_recent_messages fakeados.
# ---------------------------------------------------------------------------


class _FakeStorage:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows

    def read_series(self, series: str) -> list[dict[str, Any]]:
        assert series == basecamp_publisher._PUBLICATIONS_SERIES
        return [dict(r) for r in self.rows]

    def append_series(self, series: str, entry: dict[str, Any]) -> None:
        self.rows.append(entry)

    def write_series(self, series: str, entries: list[dict[str, Any]]) -> None:
        self.rows = list(entries)


def _auth_profile() -> AuthProfile:
    return AuthProfile(id="ap1", provider="basecamp", account="acme", access_token="tok")


def _pending_row(attempts: int = 0, created_at: str | None = None) -> dict[str, Any]:
    created_at = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return BasecampPublication(
        sprint_id="ct1",
        project_id="p1",
        event_type="sprint.started",
        bucket_id="b1",
        message_board_id="mb1",
        status="pending",
        attempts=attempts,
        created_at=created_at,
    ).model_dump(mode="json")


def _project() -> dict[str, Any]:
    return {"id": "p1", "basecamp": {"account_id": "acme", "project_id": "b1", "publish": {"enabled": True}}}


def _payload() -> SprintStartedPayload:
    return SprintStartedPayload(sprint_name="Sprint 1", period={"start": "a", "end": "b"}, committed=1)


def test_retry_respeta_backoff_no_reintenta_antes_de_tiempo(monkeypatch):
    row = _pending_row(attempts=0)  # backoff = 2s, created_at = ahora
    storage = _FakeStorage([row])
    monkeypatch.setattr(basecamp_publisher, "get_storage", lambda: storage)

    async def _boom(*args, **kwargs):
        raise AssertionError("no debería llamar a publish_message si el backoff no elapsó")

    monkeypatch.setattr(basecamp_publisher, "publish_message", _boom)

    result = asyncio.run(retry_publication(row["id"], _auth_profile(), _project(), _payload()))
    assert result.status == "pending"
    assert result.attempts == 0  # no tocado


def test_retry_reintenta_cuando_backoff_elapso(monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
    row = _pending_row(attempts=0, created_at=old)  # backoff 2s, ya pasaron 10s
    storage = _FakeStorage([row])
    monkeypatch.setattr(basecamp_publisher, "get_storage", lambda: storage)

    async def _no_recent(*args, **kwargs):
        return []

    async def _publish_ok(*args, **kwargs):
        return {"status_code": 201, "body": {"id": 999, "app_url": "https://x"}, "headers": {}}

    monkeypatch.setattr(basecamp_publisher, "list_recent_messages", _no_recent)
    monkeypatch.setattr(basecamp_publisher, "publish_message", _publish_ok)

    result = asyncio.run(retry_publication(row["id"], _auth_profile(), _project(), _payload()))
    assert result.status == "sent"
    assert result.attempts == 1
    assert storage.rows[0]["status"] == "sent"  # se reescribió la serie


def test_retry_precheck_evita_duplicar_si_ya_existe_el_mensaje(monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
    row = _pending_row(attempts=0, created_at=old)
    storage = _FakeStorage([row])
    monkeypatch.setattr(basecamp_publisher, "get_storage", lambda: storage)

    subject, _ = render_sprint_started(_payload())

    async def _found_existing(*args, **kwargs):
        return [{"subject": subject, "id": 42, "app_url": "https://existing"}]

    async def _boom(*args, **kwargs):
        raise AssertionError("no debería publicar de nuevo si ya existe el mensaje")

    monkeypatch.setattr(basecamp_publisher, "list_recent_messages", _found_existing)
    monkeypatch.setattr(basecamp_publisher, "publish_message", _boom)

    result = asyncio.run(retry_publication(row["id"], _auth_profile(), _project(), _payload()))
    assert result.status == "sent"
    assert result.basecamp_message_id == "42"


def test_retry_es_no_op_si_ya_esta_sent(monkeypatch):
    row = _pending_row()
    row["status"] = "sent"
    storage = _FakeStorage([row])
    monkeypatch.setattr(basecamp_publisher, "get_storage", lambda: storage)

    async def _boom(*args, **kwargs):
        raise AssertionError("no debería tocar nada si ya está sent")

    monkeypatch.setattr(basecamp_publisher, "publish_message", _boom)
    monkeypatch.setattr(basecamp_publisher, "list_recent_messages", _boom)

    result = asyncio.run(retry_publication(row["id"], _auth_profile(), _project(), _payload()))
    assert result.status == "sent"


def test_sweep_orphans_toca_solo_pending_viejos(monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
    recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    old_row = _pending_row(created_at=old)
    recent_row = _pending_row(created_at=recent)
    recent_row["id"] = recent_row["id"] + "-recent"
    storage = _FakeStorage([old_row, recent_row])
    monkeypatch.setattr(basecamp_publisher, "get_storage", lambda: storage)

    async def _no_recent(*args, **kwargs):
        return []

    async def _publish_ok(*args, **kwargs):
        return {"status_code": 201, "body": {"id": 1, "app_url": "https://x"}, "headers": {}}

    monkeypatch.setattr(basecamp_publisher, "list_recent_messages", _no_recent)
    monkeypatch.setattr(basecamp_publisher, "publish_message", _publish_ok)

    project = _project()
    project["memory"] = {"sprints": {"current": 1}}

    def _lookup(project_id: str):
        return (_auth_profile(), project) if project_id == "p1" else None

    touched = asyncio.run(sweep_orphans(_lookup))
    assert len(touched) == 1
    assert touched[0].id == old_row["id"]
