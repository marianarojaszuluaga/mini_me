"""Real behavior of the Drive client — including the exact failure mode a
pre-scope-change Auth Profile hits (403), not just the happy path."""

import asyncio

import httpx
import pytest

from app.schemas.auth_profile import AuthProfile
from app.services.google_drive_client import GoogleDriveError, get_file_text, list_files_in_folder


def _profile(token="real-token"):
    return AuthProfile(
        id="ap1", provider="google", account="mariana", scope="drive", access_token=token, auth_method="oauth"
    )


def test_no_token_raises():
    with pytest.raises(GoogleDriveError):
        asyncio.run(list_files_in_folder(_profile(token=None), "folder123"))


def test_lists_files(monkeypatch):
    async def fake_get(self, url, headers=None, params=None, **kwargs):
        assert "folder123" in params["q"]
        return httpx.Response(
            200, json={"files": [{"id": "f1", "name": "Acta reunión", "mimeType": "application/vnd.google-apps.document"}]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    files = asyncio.run(list_files_in_folder(_profile(), "folder123"))
    assert files[0]["name"] == "Acta reunión"


def test_403_raises_reconnect_error(monkeypatch):
    async def fake_get(self, url, headers=None, params=None, **kwargs):
        return httpx.Response(403, text="insufficient scope", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with pytest.raises(GoogleDriveError, match="[Rr]econectá"):
        asyncio.run(get_file_text(_profile(), "file123"))
