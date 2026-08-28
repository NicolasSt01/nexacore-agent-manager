"""Channel-agnostic inbound message pipeline.

Shared by the Baileys bridge endpoint, the WhatsApp Cloud webhook and the Meta
Messenger/Instagram webhook: dedupe by external message id, find or create the
conversation, resolve media into text, store the visitor message, and produce
the AI reply unless a human operator has taken over. The caller is responsible
for actually delivering the reply.
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Agent, Conversation, Message, now_utc
from .history import build_messages
from .summary import refresh_if_needed, usable_summary
from .knowledge import build_system_prompt, retrieve_knowledge
from .media import describe_image, transcribe_audio
from .providers import resolve_agent_credentials, resolve_provider_credentials
from .tools import run_completion
from .quota import QuotaExceeded, check_quota, mark_blocked, should_warn, mark_warned
from .subscription import get_pool_state, resolve_model
from .notifications import notify_quota_blocked, notify_quota_warning
from .usage import record_usage


@dataclass
class InboundMessage:
    external_message_id: str
    external_chat_id: str
    sender_name: str | None = None
    text: str = ""
    media_kind: str | None = None
    media_bytes: bytes | None = None
    media_mime: str | None = None
    # Pre-signed attachment URL, when the channel delivers one instead of a
    # media id the caller has to resolve (Messenger/Instagram do).
    media_url: str | None = None


@dataclass
class InboundResult:
    accepted: bool
    reply: str | None = None
    conversation_id: uuid.UUID | None = None
    mode: str | None = None
    outbound_message_id: uuid.UUID | None = None
    # True when the reply was deferred to let the contact finish writing; the
    # caller must not treat the missing reply as a failure.
    deferred: bool = False


def _media_placeholder(kind: str) -> str:
    return "[El cliente envió una imagen]" if kind == "image" else "[El cliente envió una nota de voz]"


async def _inbound_content(db: Session, agent: Agent, inbound: InboundMessage) -> str:
    """Resolve the effective user text, transcribing/describing media when the
    agent's capabilities allow it. Best-effort: falls back to a placeholder."""
    text = (inbound.text or "").strip()
    if not inbound.media_kind:
        return text
    if not inbound.media_bytes:
        return text or _media_placeholder(inbound.media_kind)
    enabled = (inbound.media_kind == "image" and agent.image_enabled) or (
        inbound.media_kind == "audio" and agent.audio_enabled
    )
    credentials = resolve_provider_credentials(db, agent.agency_id, "openai")
    if not enabled or not credentials:
        return text or _media_placeholder(inbound.media_kind)
    try:
        data = inbound.media_bytes
        base_url, api_key = credentials
        if inbound.media_kind == "image":
            model = agent.image_model.strip() or agent.model.strip()
            instruction = (
                "Describe con detalle el contenido de esta imagen para que un asistente pueda responder al cliente."
                + (f" El cliente escribió: {text}" if text else "")
            )
            description = await describe_image(base_url, api_key, model, data, inbound.media_mime or "image/jpeg", instruction)
            return (f"{text}\n\n" if text else "") + f"[Imagen recibida] {description}"
        model = agent.audio_model.strip() or "whisper-1"
        transcript = await transcribe_audio(base_url, api_key, model, data, "audio.ogg", inbound.media_mime or "audio/ogg")
        return (f"{text}\n\n" if text else "") + (transcript or _media_placeholder("audio"))
    except (HTTPException, ValueError):
        return text or _media_placeholder(inbound.media_kind)


async def process_inbound(
    db: Session,
    channel,
    inbound: InboundMessage,
    *,
    conversation_channel: str,
    channel_fk_field: str,
    usage_source: str | None = None,
    default_sender_name: str = "Contact",
) -> InboundResult:
    """Run the shared pipeline for one inbound message.

    ``channel`` is any channel model exposing agency_id/client_id/agent_id,
    agent, is_enabled and last_error. ``conversation_channel`` and
    ``channel_fk_field`` select the Conversation channel label and FK column;
    ``usage_source`` tags the usage record (defaults to the channel label).
    """
    fk_column = getattr(Conversation, channel_fk_field)

    existing = db.scalar(
        select(Message)
        .join(Conversation)
        .where(
            fk_column == channel.id,
            Message.external_message_id == inbound.external_message_id,
        )
    )
    if existing:
        return InboundResult(accepted=False, conversation_id=existing.conversation_id)

    conversation = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            fk_column == channel.id,
            Conversation.external_chat_id == inbound.external_chat_id,
        )
    )
    if not conversation:
        title = (inbound.sender_name or inbound.external_chat_id.split("@")[0])[:240]
        conversation = Conversation(
            agency_id=channel.agency_id,
            client_id=channel.client_id,
            agent_id=channel.agent_id,
            external_chat_id=inbound.external_chat_id,
            contact_name=inbound.sender_name,
            title=title,
            channel=conversation_channel,
            **{channel_fk_field: channel.id},
        )
        db.add(conversation)
        db.flush()
    elif inbound.sender_name:
        conversation.contact_name = inbound.sender_name

    content = await _inbound_content(db, channel.agent, inbound)
    visitor_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
        sender_type="visitor",
        sender_name=inbound.sender_name or default_sender_name,
        external_message_id=inbound.external_message_id,
    )
    conversation.updated_at = now_utc()
    db.add(visitor_message)
    db.commit()
    if conversation.mode == "human":
        return InboundResult(accepted=True, conversation_id=conversation.id, mode="human")

    agent = channel.agent

    # People write in fragments. Waiting a few seconds lets the batch complete
    # so the agent answers the whole thought once, instead of replying to "sí"
    # while the contact is still typing the rest.
    delay = agent.reply_delay_seconds or 0
    if delay > 0:
        conversation.reply_due_at = now_utc() + timedelta(seconds=delay)
        db.commit()
        return InboundResult(accepted=True, conversation_id=conversation.id, mode="ai", deferred=True)

    return await generate_reply(db, channel, conversation, usage_source or conversation_channel)


def _pending_query(db: Session, conversation: Conversation, limit: int = 5) -> str:
    """The visitor text still awaiting an answer, newest batch first.

    Everything said since the agent last spoke, joined. Retrieving on the last
    fragment alone ("sí") would find nothing; the batch carries the intent.
    """
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit * 2)
    ).all()
    pending: list[str] = []
    for message in rows:
        if message.role != "user":
            break
        pending.append(message.content)
        if len(pending) >= limit:
            break
    return "\n".join(reversed(pending))


async def generate_reply(db: Session, channel, conversation: Conversation, usage_source: str) -> InboundResult:
    """Produce the agent's reply for everything unanswered in the conversation.

    Split out from ingestion so the deferred worker can call it once the batch
    has settled. The accumulated messages are already stored, so the prompt
    naturally contains them as consecutive turns.
    """
    agent = channel.agent
    # Hard enforcement, before the provider call: checking afterwards would mean
    # the tokens were already spent.
    try:
        check_quota(db, channel.client, source=usage_source)
    except QuotaExceeded:
        # The conversation drops to a human so an operator sees it in the inbox.
        # No automated "you ran out of credit" message reaches the end contact:
        # a patient messaging a clinic must never see NexaCore's billing state.
        conversation.mode = "human"
        db.commit()
        if mark_blocked(db, channel.client):
            notify_quota_blocked(db, channel.client)
        return InboundResult(accepted=True, conversation_id=conversation.id, mode="human")

    credentials = resolve_agent_credentials(db, agent)
    if not agent.is_active or not credentials or not agent.model.strip():
        channel.last_error = "A message was received, but the assigned agent is not ready (model or provider key missing)."
        channel.updated_at = now_utc()
        db.commit()
        return InboundResult(accepted=True, conversation_id=conversation.id, mode="ai")

    db.refresh(conversation)
    # Retrieve against everything the contact said in this batch, not just the
    # last fragment: "sí" on its own retrieves nothing useful.
    query = _pending_query(db, conversation)
    knowledge = await retrieve_knowledge(db, agent, query)
    # Fold any closed session into the contact card before building the prompt,
    # so a returning customer is recognised on their first message back rather
    # than one message later.
    base_url, api_key = credentials
    await refresh_if_needed(db, agent, conversation, base_url, api_key)
    messages = build_messages(
        db,
        agent,
        conversation.id,
        build_system_prompt(agent, knowledge.text),
        contact_summary=usable_summary(conversation),
    )
    # Circuit breaker on the shared subscription pool. Degrading to a model
    # that does not consume it keeps every client answering; without this, one
    # exhausted pool silences the whole portfolio at once.
    pool = get_pool_state(db, agent.agency_id, agent.provider)
    if pool.blocked:
        conversation.mode = "human"
        channel.last_error = (
            f"The {pool.provider} subscription pool is at {pool.percent:.0f}%. "
            "Conversations were handed over to a human."
        )
        channel.updated_at = now_utc()
        db.commit()
        return InboundResult(accepted=True, conversation_id=conversation.id, mode="human")
    model_used, swapped = resolve_model(pool, agent.model)

    try:
        completion = await run_completion(
            db,
            agent,
            base_url,
            api_key,
            messages,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            model_override=model_used if swapped else None,
        )
    except Exception as exc:
        channel.last_error = f"Message received, but the agent could not reply: {str(exc)[:400]}"
        channel.updated_at = now_utc()
        db.commit()
        return InboundResult(accepted=True, conversation_id=conversation.id, mode="ai")

    outbound = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=completion.text,
        sources=knowledge.sources,
        tool_calls=completion.tool_calls,
        sender_type="ai",
        sender_name=agent.name,
    )
    record_usage(db, agent.agency_id, agent.client_id, agent.id, agent.provider, model_used.strip(), completion, source=usage_source)
    conversation.updated_at = now_utc()
    channel.last_error = None
    db.add(outbound)
    db.commit()
    if should_warn(db, channel.client):
        mark_warned(db, channel.client)
        notify_quota_warning(db, channel.client)
    return InboundResult(
        accepted=True,
        reply=completion.text,
        conversation_id=conversation.id,
        mode="ai",
        outbound_message_id=outbound.id,
    )
