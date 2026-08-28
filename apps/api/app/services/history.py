"""Conversation history for the model prompt.

Three rules, all per agent:

1. **Session cut.** A gap longer than `session_gap_hours` between two messages
   ends a session. A morning enquiry and its afternoon follow-up are the same
   conversation; the next day is not.
2. **Age cap.** Raw messages older than `history_max_age_days` never enter the
   prompt, even if the count would allow them.
3. **Count cap.** At most `memory_limit` messages.

Each message also carries a relative time marker (`[hace 2 días]`). Without it
the model sees a flat list with no sense of when anything was said, and starts
answering "como quedamos el lunes" about a Monday three weeks gone — an error
the patient sees.

This is the single place history is assembled. It used to be duplicated across
three call sites, each subtly different.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Agent, Message, now_utc


# Below this, a message is "just now" and a marker would be noise.
RECENT_SECONDS = 15 * 60


def aware(value: datetime) -> datetime:
    """Timestamps come back timezone-aware from PostgreSQL but naive from
    SQLite, which is what local development and the test suite use. Comparing
    the two raises, so normalise to UTC before any arithmetic."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def relative_marker(delta: timedelta) -> str:
    """Human phrase for how long ago something was said, in Spanish — it goes
    into the prompt, which is the customer's language."""
    seconds = max(0, int(delta.total_seconds()))
    if seconds < RECENT_SECONDS:
        return ""
    minutes = seconds // 60
    if minutes < 60:
        return f"[hace {minutes} min]"
    hours = minutes // 60
    if hours < 24:
        return f"[hace {hours} h]" if hours > 1 else "[hace 1 h]"
    days = hours // 24
    if days == 1:
        return "[ayer]"
    if days < 30:
        return f"[hace {days} días]"
    months = days // 30
    return "[hace 1 mes]" if months == 1 else f"[hace {months} meses]"


def _session_start_index(messages: list[Message], gap: timedelta) -> int:
    """Index of the first message of the current session.

    Walks backwards and cuts at the first gap wider than `gap`.
    """
    for index in range(len(messages) - 1, 0, -1):
        if aware(messages[index].created_at) - aware(messages[index - 1].created_at) > gap:
            return index
    return 0


def session_boundary(db: Session, agent: Agent, conversation_id: uuid.UUID) -> datetime | None:
    """When the current session started, or None if there is no earlier one.

    Everything before this point is what the contact summary has to carry, so
    the agent still knows who it is talking to without dragging the transcript.
    """
    gap_hours = agent.session_gap_hours or 0
    if gap_hours <= 0:
        return None
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(max(agent.memory_limit or 20, 20) * 3)
    ).all()
    messages = list(reversed(rows))
    if len(messages) < 2:
        return None
    index = _session_start_index(messages, timedelta(hours=gap_hours))
    return aware(messages[index].created_at) if index > 0 else None


def select_history(db: Session, agent: Agent, conversation_id: uuid.UUID) -> list[Message]:
    """Messages that should enter the prompt, oldest first."""
    limit = agent.memory_limit or 0
    if limit <= 0:
        return []

    # Read a bit more than the cap so the session cut has room to work; without
    # the margin, a long session would be cut by the count before the gap.
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit * 3)
    ).all()
    messages = list(reversed(rows))
    if not messages:
        return []

    gap_hours = agent.session_gap_hours or 0
    if gap_hours > 0:
        messages = messages[_session_start_index(messages, timedelta(hours=gap_hours)):]

    max_age_days = agent.history_max_age_days or 0
    if max_age_days > 0:
        cutoff = now_utc() - timedelta(days=max_age_days)
        messages = [message for message in messages if aware(message.created_at) >= cutoff]

    return messages[-limit:]


def build_messages(
    db: Session,
    agent: Agent,
    conversation_id: uuid.UUID,
    system_prompt: str,
    *,
    contact_summary: str = "",
) -> list[dict[str, str]]:
    """The full message list for the provider: system prompt, optional contact
    summary, then the selected history with time markers."""
    history = select_history(db, agent, conversation_id)
    now = now_utc()

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if contact_summary.strip():
        # Phase 2 hook: carries continuity across sessions at a fixed cost,
        # instead of dragging the whole transcript along.
        messages.append({
            "role": "system",
            "content": f"FICHA DEL CONTACTO (de conversaciones anteriores):\n{contact_summary.strip()}",
        })

    for message in history:
        marker = relative_marker(now - aware(message.created_at))
        content = f"{marker} {message.content}" if marker else message.content
        messages.append({"role": message.role, "content": content})
    return messages
