"""Token quota enforcement.

One gate, called before every LLM request. Checking after the fact would mean
the tokens were already spent, which is exactly what the limit exists to
prevent.

Enforcement is hard: when a client's package runs out, automatic replies stop
and the conversation falls back to a human. What the end contact sees differs
per channel and is the caller's decision — see the handlers.
"""

import logging

from sqlalchemy.orm import Session

from ..models import Client, now_utc
from .billing import NON_BILLABLE_SOURCES, get_quota_status


logger = logging.getLogger("nexacore.quota")

# Share of the package that triggers the heads-up email, once per cycle.
WARNING_THRESHOLD_PCT = 80.0


class QuotaExceeded(Exception):
    """The client's package is spent for the current cycle."""

    def __init__(self, client: Client, used: int, limit: int):
        self.client = client
        self.used = used
        self.limit = limit
        super().__init__(f"Client {client.id} used {used} of {limit} tokens this cycle")


def check_quota(db: Session, client: Client, *, source: str = "") -> None:
    """Raise QuotaExceeded when the client cannot spend more tokens.

    No-op for BYOK (the client pays their own provider), for an unlimited plan,
    and for non-billable sources such as the internal playground — NexaCore
    testing an agent must not consume the client's package.
    """
    if source in NON_BILLABLE_SOURCES:
        return
    if client.billing_mode == "byok":
        return
    if not client.monthly_token_limit:
        return

    status = get_quota_status(db, client)
    if not status["is_blocked"]:
        return
    raise QuotaExceeded(client, status["used_tokens"], status["limit_tokens"])


def mark_blocked(db: Session, client: Client) -> bool:
    """Stamp the moment the block engaged in this cycle.

    Returns True the first time only, so the notification fires once per cycle
    rather than on every message that arrives after the limit.
    """
    cycle_start = get_quota_status(db, client)["cycle_start"]
    if client.quota_blocked_at and client.quota_blocked_at >= cycle_start:
        return False
    client.quota_blocked_at = now_utc()
    db.commit()
    return True


def should_warn(db: Session, client: Client) -> bool:
    """Whether the 80% heads-up is due, at most once per cycle."""
    if client.billing_mode == "byok" or not client.monthly_token_limit:
        return False
    status = get_quota_status(db, client)
    if status["percentage_used"] < WARNING_THRESHOLD_PCT or status["is_blocked"]:
        return False
    if client.quota_warned_at and client.quota_warned_at >= status["cycle_start"]:
        return False
    return True


def mark_warned(db: Session, client: Client) -> None:
    client.quota_warned_at = now_utc()
    db.commit()
