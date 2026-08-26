"""Public webhook for the Messenger / Instagram channels.

Same contract as the WhatsApp Cloud webhook: a GET handshake when the webhook
is registered, and signed POSTs for inbound traffic, verified with HMAC-SHA256
over the raw bytes before the payload is parsed.

Messenger and Instagram share this handler: the payload shape is identical and
only the envelope `object` differs, which is validated against the channel's
platform so a Page event cannot be delivered to an Instagram channel.
"""

import hashlib
import hmac
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Message, MetaMessagingChannel, now_utc
from ..ratelimit import whatsapp_cloud_webhook_rate_limit
from ..security import decrypt_secret
from ..services.meta_messaging import WEBHOOK_OBJECT, fetch_attachment, fetch_contact_name, send_text
from ..services.whatsapp_inbound import InboundMessage, process_inbound


public_router = APIRouter(prefix="/public/meta", tags=["Messenger/Instagram public"])

# Attachment types the pipeline can turn into text; anything else is ignored.
SUPPORTED_ATTACHMENTS = {"image": "image", "audio": "audio"}


def _channel(db: Session, channel_id: uuid.UUID) -> MetaMessagingChannel:
    channel = db.get(MetaMessagingChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Unknown channel")
    return channel


@public_router.get("/channels/{channel_id}/webhook")
def verify_webhook(
    channel_id: uuid.UUID,
    db: Session = Depends(get_db),
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    channel = _channel(db, channel_id)
    if (
        hub_mode != "subscribe"
        or not channel.webhook_verify_token
        or not hmac.compare_digest(hub_verify_token, channel.webhook_verify_token)
    ):
        raise HTTPException(status_code=403, detail="Verification failed")
    return PlainTextResponse(hub_challenge)


def _parse_event(event: dict) -> InboundMessage | None:
    """Map one messaging event to the shared inbound shape; None to skip."""
    message = event.get("message") or {}
    # Echoes are our own outbound messages coming back. Processing them would
    # make the agent answer itself in a loop.
    if message.get("is_echo"):
        return None
    sender = (event.get("sender") or {}).get("id") or ""
    mid = message.get("mid") or ""
    if not sender or not mid:
        return None

    text = message.get("text") or ""
    for attachment in message.get("attachments") or []:
        kind = SUPPORTED_ATTACHMENTS.get(attachment.get("type") or "")
        if not kind:
            continue
        url = (attachment.get("payload") or {}).get("url")
        if not url:
            continue
        return InboundMessage(
            external_message_id=mid,
            external_chat_id=sender,
            text=text,
            media_kind=kind,
            media_url=url,
        )
    if not text.strip():
        return None
    return InboundMessage(external_message_id=mid, external_chat_id=sender, text=text)


@public_router.post(
    "/channels/{channel_id}/webhook",
    dependencies=[Depends(whatsapp_cloud_webhook_rate_limit)],
)
async def receive_webhook(channel_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    channel = _channel(db, channel_id)
    if not channel.encrypted_app_secret:
        raise HTTPException(status_code=403, detail="Channel is not configured")
    raw = await request.body()
    app_secret = decrypt_secret(channel.encrypted_app_secret)
    expected = "sha256=" + hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    signature = request.headers.get("X-Hub-Signature-256") or ""
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # From here on always acknowledge with 200: Meta retries non-2xx responses,
    # and a payload that fails once will fail on every retry.
    try:
        payload = json.loads(raw)
    except ValueError:
        return {"status": "ok"}
    if not channel.is_enabled:
        return {"status": "ok"}
    # A Page event must not be handled by an Instagram channel, or vice versa.
    if payload.get("object") != WEBHOOK_OBJECT.get(channel.platform):
        return {"status": "ok"}

    access_token = decrypt_secret(channel.encrypted_access_token) if channel.encrypted_access_token else None
    for entry in payload.get("entry") or []:
        for event in entry.get("messaging") or []:
            inbound = _parse_event(event)
            if not inbound:
                continue
            await _handle_message(db, channel, inbound, access_token)
    return {"status": "ok"}


async def _handle_message(
    db: Session,
    channel: MetaMessagingChannel,
    inbound: InboundMessage,
    access_token: str | None,
) -> None:
    if inbound.media_url:
        downloaded = await fetch_attachment(inbound.media_url)
        if downloaded:
            inbound.media_bytes, inbound.media_mime = downloaded
    if access_token and not inbound.sender_name:
        inbound.sender_name = await fetch_contact_name(access_token, inbound.external_chat_id)

    label = "Messenger contact" if channel.platform == "messenger" else "Instagram contact"
    try:
        result = await process_inbound(
            db,
            channel,
            inbound,
            conversation_channel=channel.platform,
            channel_fk_field="meta_channel_id",
            default_sender_name=label,
        )
    except Exception as exc:
        channel.last_error = f"An inbound message could not be processed: {str(exc)[:400]}"
        channel.updated_at = now_utc()
        db.commit()
        return
    if not result.reply or not access_token or not channel.account_id:
        return
    try:
        message_id = await send_text(access_token, channel.account_id, inbound.external_chat_id, result.reply)
    except HTTPException as exc:
        channel.last_error = f"The reply could not be sent: {exc.detail}"
        channel.updated_at = now_utc()
        db.commit()
        return
    if message_id and result.outbound_message_id:
        message = db.get(Message, result.outbound_message_id)
        if message:
            message.external_message_id = message_id
            db.commit()
