"""Deferred replies: answer once the contact has finished writing.

People write in fragments — "sí", then "para el lunes", then "en la mañana".
Answering the first one produces three replies to half a thought and reads like
a machine. So each inbound message sets `Conversation.reply_due_at` a few
seconds out, and every new message pushes it forward. When it finally settles,
this worker answers the whole batch once.

The marker lives in the database rather than in an in-memory timer, so a
restart cannot strand a customer waiting for an answer that will never come.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Conversation, MetaMessagingChannel, Message, WhatsAppChannel, WhatsAppCloudChannel, now_utc
from .whatsapp import send_channel_message
from .whatsapp_inbound import generate_reply


logger = logging.getLogger("nexacore.replies")

# How often the worker looks for settled batches. Adds at most this much on top
# of the agent's own delay.
POLL_SECONDS = 2
# Safety valve: never process more than this per tick, so one busy moment
# cannot starve the loop.
BATCH_LIMIT = 25


def _channel_for(db: Session, conversation: Conversation):
    """The channel object a conversation arrived through, or None."""
    if conversation.whatsapp_channel_id:
        return db.get(WhatsAppChannel, conversation.whatsapp_channel_id)
    if conversation.whatsapp_cloud_channel_id:
        return db.get(WhatsAppCloudChannel, conversation.whatsapp_cloud_channel_id)
    if conversation.meta_channel_id:
        return db.get(MetaMessagingChannel, conversation.meta_channel_id)
    return None


def due_conversations(db: Session) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.reply_due_at.is_not(None), Conversation.reply_due_at <= now_utc())
            .order_by(Conversation.reply_due_at.asc())
            .limit(BATCH_LIMIT)
        ).all()
    )


async def answer_one(db: Session, conversation: Conversation) -> bool:
    """Generate and deliver the reply for one settled conversation."""
    # An operator may have taken over while the batch was settling.
    if conversation.mode == "human":
        conversation.reply_due_at = None
        db.commit()
        return False

    channel = _channel_for(db, conversation)
    if channel is None or not getattr(channel, "is_enabled", True):
        conversation.reply_due_at = None
        db.commit()
        return False

    try:
        result = await generate_reply(db, channel, conversation, conversation.channel)
    finally:
        # The worker owns the marker: whatever the outcome, this batch has been
        # dealt with. Leaving it set would re-answer the same messages every
        # two seconds. (generate_reply cannot clear it itself — it calls
        # db.refresh(), which would reload the old value.)
        conversation.reply_due_at = None
        db.commit()

    if not result.reply:
        return False

    try:
        external_id = await send_channel_message(db, conversation, result.reply)
    except Exception as exc:  # noqa: BLE001 - a delivery failure must not stop the loop
        channel.last_error = f"The reply could not be sent: {str(exc)[:400]}"
        channel.updated_at = now_utc()
        db.commit()
        return False

    if external_id and result.outbound_message_id:
        message = db.get(Message, result.outbound_message_id)
        if message:
            message.external_message_id = external_id
            db.commit()
    return True


async def process_due(db: Session) -> int:
    """One pass over the settled conversations. Returns how many were answered."""
    answered = 0
    for conversation in due_conversations(db):
        try:
            if await answer_one(db, conversation):
                answered += 1
        except Exception as exc:  # noqa: BLE001 - one bad conversation must not stop the rest
            logger.warning("Deferred reply failed for %s: %s", conversation.id, exc)
            db.rollback()
            conversation.reply_due_at = None
            db.commit()
    return answered


async def worker_loop() -> None:
    """Poll for settled batches until cancelled at shutdown."""
    while True:
        try:
            await asyncio.sleep(POLL_SECONDS)
        except asyncio.CancelledError:
            raise
        db = SessionLocal()
        try:
            await process_due(db)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop must survive anything
            logger.warning("Deferred reply worker raised: %s", exc)
        finally:
            db.close()
