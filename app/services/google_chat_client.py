"""Google Chat — incoming webhook messages.

Closes the gap flagged in `leo_testconsolidator.md`: unlike Drive (needs a
new OAuth scope + reconnect), a Chat "incoming webhook" is just a per-space
URL a Chat space admin generates (Space settings > Apps & integrations >
Add webhook) — no OAuth Auth Profile needed at all. This is why it's
implemented directly, not blocked like Drive.
"""

from __future__ import annotations

from typing import Any

import httpx


class GoogleChatError(RuntimeError):
    """Raised on any real failure sending a Chat message — never fabricate success."""


async def send_message(webhook_url: str, text: str) -> dict[str, Any]:
    """POSTs a plain-text message to a Google Chat space via its incoming
    webhook URL. Raises GoogleChatError on any non-2xx response instead of
    swallowing it — a silent failure here means Mariana never finds out the
    QA stats never reached the channel."""
    if not webhook_url or not webhook_url.startswith("https://chat.googleapis.com/"):
        raise GoogleChatError(
            "webhook_url inválida — debe ser una URL de webhook entrante de Google Chat "
            "(Configuración del espacio > Apps e integraciones > Agregar webhook)."
        )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url, json={"text": text})

    if response.status_code >= 400:
        raise GoogleChatError(
            f"Google Chat rechazó el mensaje ({response.status_code}): {response.text[:300]}"
        )
    return response.json() if response.content else {"status": "sent"}
