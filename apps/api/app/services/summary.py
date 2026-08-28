"""The contact summary: continuity across sessions at a fixed cost.

When a session closes, its messages stop entering the prompt. Without anything
in their place the agent greets a returning patient as a stranger and asks for
their name again — which is exactly the customer worth remembering.

So the closed session is folded into a short card:

    Rodrigo Salas, tel. 33 1234 5678. Preguntó por blanqueamiento ($2,500) el
    22/08. Quedó de agendar lunes por la mañana; recepción no confirmó.

The card is regenerated (not appended to) each time, so it stays roughly the
same size no matter how many sessions accumulate. That is the whole point: raw
history grows without bound, a summary does not.
"""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Agent, Conversation, Message, now_utc
from .ai import chat_completion
from .history import aware, session_boundary
from .usage import record_usage


logger = logging.getLogger("nexacore.summary")

# Past this, the card is history rather than context: a patient who has not
# written in three months is starting a new conversation, not continuing one.
SUMMARY_VALID_DAYS = 90

# Enough for a name, a phone number and what was left pending. More than that
# and we are back to carrying a transcript.
MAX_SUMMARY_TOKENS = 220

# Messages older than this are not worth folding in; the card would describe a
# conversation neither side remembers.
MAX_SOURCE_AGE_DAYS = 180

PROMPT = (
    "Eres un asistente que resume conversaciones de atención a clientes para que otro agente "
    "pueda retomarlas después.\n\n"
    "Escribe una ficha BREVE (máximo 4 líneas) con solo lo que sirva para continuar la atención:\n"
    "- Nombre del contacto y su teléfono o correo, si los dio.\n"
    "- Qué preguntó o qué le interesa, con los precios o datos concretos que se le dieron.\n"
    "- Qué quedó pendiente o acordado.\n\n"
    "Reglas:\n"
    "- No inventes nada que no esté en la conversación.\n"
    "- No incluyas saludos, cortesías ni el detalle de cada mensaje.\n"
    "- Si ya existe una ficha previa, intégrala con lo nuevo en una sola ficha, sin repetir.\n"
    "- Escribe en español, en tercera persona, sin encabezados ni viñetas."
)


def is_valid(conversation: Conversation, at=None) -> bool:
    """Whether the stored card is recent enough to put in the prompt."""
    if not conversation.contact_summary.strip() or not conversation.contact_summary_through:
        return False
    age = (at or now_utc()) - aware(conversation.contact_summary_through)
    return age <= timedelta(days=SUMMARY_VALID_DAYS)


def usable_summary(conversation: Conversation) -> str:
    return conversation.contact_summary if is_valid(conversation) else ""


def _pending_messages(db: Session, conversation: Conversation, boundary) -> list[Message]:
    """Closed-session messages not yet folded into the card."""
    stmt = select(Message).where(
        Message.conversation_id == conversation.id, Message.created_at < boundary
    )
    if conversation.contact_summary_through:
        stmt = stmt.where(Message.created_at > conversation.contact_summary_through)
    stmt = stmt.where(Message.created_at >= now_utc() - timedelta(days=MAX_SOURCE_AGE_DAYS))
    return list(db.scalars(stmt.order_by(Message.created_at.asc())).all())


async def refresh_if_needed(
    db: Session,
    agent: Agent,
    conversation: Conversation,
    base_url: str,
    api_key: str,
) -> bool:
    """Rebuild the card when a session has closed since the last one.

    Returns True if it was regenerated. Costs one short completion per session
    transition — far less than the history it replaces. Never raises: failing
    to summarise must not stop the reply the customer is waiting for.
    """
    boundary = session_boundary(db, agent, conversation.id)
    if boundary is None:
        return False

    pending = _pending_messages(db, conversation, boundary)
    if not pending:
        return False

    transcript = "\n".join(
        f"{'Cliente' if message.role == 'user' else 'Agente'}: {message.content[:600]}"
        for message in pending
    )
    previous = usable_summary(conversation)
    user_content = (
        (f"FICHA PREVIA:\n{previous}\n\n" if previous else "")
        + f"CONVERSACIÓN A RESUMIR:\n{transcript}"
    )

    try:
        completion = await chat_completion(
            agent.provider,
            base_url,
            api_key,
            agent.model.strip(),
            [{"role": "system", "content": PROMPT}, {"role": "user", "content": user_content}],
            temperature=0.2,
            max_tokens=MAX_SUMMARY_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001 - a missing summary is not worth a failed reply
        logger.warning("Could not refresh the contact summary for %s: %s", conversation.id, exc)
        return False

    text = (completion.text or "").strip()
    if not text:
        return False

    conversation.contact_summary = text
    conversation.contact_summary_through = pending[-1].created_at
    # Recorded like any other usage, tagged so it is visible as an internal
    # cost rather than mistaken for a customer conversation.
    record_usage(
        db,
        agent.agency_id,
        agent.client_id,
        agent.id,
        agent.provider,
        agent.model.strip(),
        completion,
        source="summary",
    )
    db.commit()
    return True
