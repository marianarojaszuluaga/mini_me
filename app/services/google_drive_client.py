"""Google Drive client — closes the gap flagged in `mia_meetingmessenger.md`
(read meeting notes) and `nico_docsync.md` (write finalized docs).

Auth: reuses the Google Auth Profile's OAuth access_token (same one
app/routers/oauth.py's Google flow sets, now requesting drive.readonly +
drive.file — see that file's 2026-09-17 comment). Any Auth Profile
connected BEFORE that scope change must be reconnected — its existing
token does NOT retroactively gain Drive access; this client will raise
GoogleDriveError (403) in that case, never fabricate empty results.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas.auth_profile import AuthProfile

_API_BASE = "https://www.googleapis.com/drive/v3"
_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
_DOC_MIME = "application/vnd.google-apps.document"


class GoogleDriveError(RuntimeError):
    """Real, explicit failure talking to the Drive API — never swallowed
    into a fabricated empty/success response."""


def _headers(auth_profile: AuthProfile) -> dict[str, str]:
    if not auth_profile.access_token:
        raise GoogleDriveError("El Auth Profile de Google no tiene un access_token real conectado.")
    return {"Authorization": f"Bearer {auth_profile.access_token}"}


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise GoogleDriveError("El token de Google expiró o fue revocado — reconectá el Auth Profile.")
    if response.status_code == 403:
        raise GoogleDriveError(
            "Google Drive rechazó el pedido (403) — probablemente el Auth Profile se conectó antes de "
            "que Mini me pidiera scopes de Drive. Reconectá el Auth Profile de Google para renovarlos."
        )
    if response.status_code == 404:
        raise GoogleDriveError("El archivo o carpeta de Drive no existe o no es accesible con este token.")
    if response.status_code >= 400:
        raise GoogleDriveError(f"Google Drive devolvió un error real ({response.status_code}): {response.text[:300]}")


async def list_files_in_folder(auth_profile: AuthProfile, folder_id: str) -> list[dict[str, Any]]:
    """Lists non-trashed files directly inside a Drive folder — used by `mia`
    to look for a meeting's notes doc, and by `nico` to check what already
    exists before uploading."""
    headers = _headers(auth_profile)
    params = {
        "q": f"'{folder_id}' in parents and trashed = false",
        "fields": "files(id, name, mimeType, modifiedTime)",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{_API_BASE}/files", headers=headers, params=params)
    _raise_for_status(response)
    return response.json().get("files", [])


async def get_file_text(auth_profile: AuthProfile, file_id: str) -> str:
    """Reads a Google Doc's plain-text content (exported), for `mia` to hand
    a meeting note to `santi` verbatim."""
    headers = _headers(auth_profile)
    params = {"mimeType": "text/plain"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{_API_BASE}/files/{file_id}/export", headers=headers, params=params)
    _raise_for_status(response)
    return response.text


async def create_doc(
    auth_profile: AuthProfile, folder_id: str, name: str, plain_text_content: str
) -> dict[str, Any]:
    """Creates a new Google Doc inside `folder_id` from plain text — what
    `nico` uses to push a finalized repo file to Drive as a real Doc, not a
    raw .md upload. Two real API calls (create metadata, then upload media)
    because Drive's `multipart` upload for a Google-native doc conversion
    needs the content as plain text in the body, not JSON."""
    headers = _headers(auth_profile)
    metadata = {"name": name, "mimeType": _DOC_MIME, "parents": [folder_id]}

    boundary = "mini_me_drive_upload"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f'{{"name": "{name}", "mimeType": "{_DOC_MIME}", "parents": ["{folder_id}"]}}\r\n'
        f"--{boundary}\r\n"
        f"Content-Type: text/plain\r\n\r\n"
        f"{plain_text_content}\r\n"
        f"--{boundary}--"
    )
    upload_headers = {**headers, "Content-Type": f"multipart/related; boundary={boundary}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{_UPLOAD_BASE}/files?uploadType=multipart",
            headers=upload_headers,
            content=body,
        )
    _raise_for_status(response)
    return response.json()
