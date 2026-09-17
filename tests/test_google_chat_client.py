"""Real behavior of the Google Chat webhook client — no mocked-success, both
the happy path and the two ways it can genuinely fail."""

import asyncio

import httpx
import pytest

from app.services.google_chat_client import GoogleChatError, send_message


def test_rejects_non_chat_webhook_url():
    with pytest.raises(GoogleChatError):
        asyncio.run(send_message("https://example.com/webhook", "hola"))


def test_sends_message_on_2xx(monkeypatch):
    async def fake_post(self, url, json=None, **kwargs):
        assert json == {"text": "3 pasaron, 1 falló"}
        return httpx.Response(200, json={"name": "spaces/x/messages/y"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = asyncio.run(
        send_message("https://chat.googleapis.com/v1/spaces/x/messages?key=abc", "3 pasaron, 1 falló")
    )
    assert result["name"] == "spaces/x/messages/y"


def test_raises_on_error_response(monkeypatch):
    async def fake_post(self, url, json=None, **kwargs):
        return httpx.Response(403, text="PERMISSION_DENIED", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(GoogleChatError):
        asyncio.run(send_message("https://chat.googleapis.com/v1/spaces/x/messages?key=abc", "hola"))
