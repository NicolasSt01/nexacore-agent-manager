"""Thin client for the Meta Messenger Platform (Facebook Messenger + Instagram).

Both platforms share one Send API and one webhook shape; only the object type
and the account id differ, so the same functions serve both. Each channel brings
its own Meta app credentials; the access token is decrypted by the caller and
never logged.
"""

import httpx
from fastapi import HTTPException

from ..config import get_settings


MESSENGER = "messenger"
INSTAGRAM = "instagram"
PLATFORMS = (MESSENGER, INSTAGRAM)

# Meta rejects Send API text bodies longer than this.
MAX_TEXT_LENGTH = 2000
MAX_MEDIA_BYTES = 20 * 1024 * 1024
GRAPH_TIMEOUT = 30

# The `object` value Meta puts on the webhook envelope, per platform.
WEBHOOK_OBJECT = {MESSENGER: "page", INSTAGRAM: "instagram"}


def _graph_url(path: str) -> str:
    return f"{get_settings().meta_graph_base_url.rstrip('/')}/{path.lstrip('/')}"


def _graph_error(response: httpx.Response) -> str:
    try:
        message = response.json().get("error", {}).get("message")
    except ValueError:
        message = None
    return message or f"Meta API returned status {response.status_code}"


async def _graph_request(method: str, url: str, access_token: str, **kwargs) -> httpx.Response:
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with httpx.AsyncClient(timeout=GRAPH_TIMEOUT, follow_redirects=True) as client:
            return await client.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the Meta API.") from exc


async def verify_account(access_token: str, platform: str, account_id: str) -> dict:
    """Validate the credentials and return the account's public profile."""
    fields = "name" if platform == MESSENGER else "username,name"
    response = await _graph_request("GET", _graph_url(f"{account_id}?fields={fields}"), access_token)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Credential check failed: {_graph_error(response)}")
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid response from the Meta API.") from exc


async def send_text(access_token: str, account_id: str, recipient_id: str, body: str) -> str | None:
    """Send a text message; returns Meta's outbound message id."""
    payload = {
        "recipient": {"id": recipient_id},
        # RESPONSE keeps the message inside the standard messaging window, which
        # is what an agent replying to an inbound message always is.
        "messaging_type": "RESPONSE",
        "message": {"text": body[:MAX_TEXT_LENGTH]},
    }
    response = await _graph_request("POST", _graph_url(f"{account_id}/messages"), access_token, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Meta could not send the message: {_graph_error(response)}")
    try:
        return response.json().get("message_id")
    except ValueError:
        return None


async def fetch_contact_name(access_token: str, user_id: str) -> str | None:
    """Best-effort display name for a sender. Returns None when the app lacks
    the profile permission — a missing name must never drop the message."""
    response = await _graph_request("GET", _graph_url(f"{user_id}?fields=name"), access_token)
    if response.status_code >= 400:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data.get("name") or data.get("username")


async def fetch_attachment(url: str) -> tuple[bytes, str] | None:
    """Download an inbound attachment. Unlike WhatsApp, the webhook already
    carries a pre-signed URL, so no access token is involved."""
    try:
        async with httpx.AsyncClient(timeout=GRAPH_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400 or len(response.content) > MAX_MEDIA_BYTES:
        return None
    mime = (response.headers.get("content-type") or "application/octet-stream").split(";")[0]
    return response.content, mime
