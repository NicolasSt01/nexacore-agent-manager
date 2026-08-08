import uuid

import httpx
from fastapi import HTTPException

from ..config import get_settings
from ..models import Conversation


async def bridge_command(method: str, path: str, payload: dict | None = None) -> dict:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method,
                f"{settings.whatsapp_bridge_url.rstrip('/')}{path}",
                headers={"X-Bridge-Token": settings.whatsapp_bridge_token},
                json=payload,
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="The local WhatsApp service is not available. Start it with npm run dev inside whatsapp/.",
        ) from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("error")
        except ValueError:
            detail = None
        raise HTTPException(status_code=502, detail=detail or "WhatsApp could not complete the operation")
    if response.status_code == 204:
        return {}
    return response.json()


async def send_whatsapp_message(conversation: Conversation, content: str) -> str | None:
    if conversation.channel != "whatsapp":
        return None
    if not conversation.whatsapp_channel_id or not conversation.external_chat_id:
        raise HTTPException(status_code=409, detail="This conversation does not have a valid WhatsApp destination")
    result = await bridge_command(
        "POST",
        f"/channels/{conversation.whatsapp_channel_id}/send",
        {"remote_jid": conversation.external_chat_id, "text": content},
    )
    return result.get("external_message_id")
