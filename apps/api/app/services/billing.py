"""Billing cycle windows and token quota status.

Consumption is always derived with a SUM over usage_records inside the client's
cycle window. There is deliberately no mutable "tokens used so far" counter on
the client: a counter needs a reset job, drifts when that job fails, and cannot
be audited against the records it claims to summarize.
"""

import calendar
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Client, UsageRecord


# Usage from these entry points is recorded for cost reporting but does not
# count against the client's plan: it is NexaCore testing the agent, not the
# client's end users consuming their package.
NON_BILLABLE_SOURCES = ("playground",)


class QuotaStatus(TypedDict):
    used_tokens: int
    limit_tokens: int
    percentage_used: float
    is_blocked: bool
    billing_mode: str
    monthly_fee_mxn: Decimal
    cycle_start: datetime
    cycle_end: datetime


def get_cycle_window(client: Client, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Current [start, end) cycle window, anchored to the client's signup day.

    A client registered on the 12th cuts on the 12th of every month. Anchors
    past the end of a short month are clamped to its last day (a client
    anchored on the 31st cuts on Feb 28th) so no cycle is ever skipped.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    anchor = max(1, min(31, client.billing_anchor_day or 1))

    def clamp(year: int, month: int) -> int:
        return min(anchor, calendar.monthrange(year, month)[1])

    # The cycle that contains `now` starts on this month's anchor if that day
    # has already passed, otherwise on last month's.
    if now.day >= clamp(now.year, now.month):
        start_year, start_month = now.year, now.month
    else:
        start_year, start_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)

    end_year, end_month = (start_year + 1, 1) if start_month == 12 else (start_year, start_month + 1)

    cycle_start = datetime(start_year, start_month, clamp(start_year, start_month), tzinfo=timezone.utc)
    cycle_end = datetime(end_year, end_month, clamp(end_year, end_month), tzinfo=timezone.utc)
    return cycle_start, cycle_end


def get_client_used_tokens(db: Session, client_id: uuid.UUID, start: datetime, end: datetime) -> int:
    """Billable tokens (input + output) consumed by one client within the window."""
    stmt = (
        select(func.coalesce(func.sum(UsageRecord.input_tokens + UsageRecord.output_tokens), 0))
        .where(UsageRecord.client_id == client_id)
        .where(UsageRecord.created_at >= start)
        .where(UsageRecord.created_at < end)
        .where(UsageRecord.source.not_in(NON_BILLABLE_SOURCES))
    )
    return int(db.scalar(stmt) or 0)


def get_quota_status(db: Session, client: Client) -> QuotaStatus:
    cycle_start, cycle_end = get_cycle_window(client)
    used = get_client_used_tokens(db, client.id, cycle_start, cycle_end)
    limit = client.monthly_token_limit or 0

    # BYOK spends the client's own key, and limit == 0 means unlimited: neither
    # can ever be blocked.
    is_blocked = False
    pct = 0.0
    if client.billing_mode != "byok" and limit > 0:
        pct = round((used / limit) * 100, 1)
        is_blocked = used >= limit

    return {
        "used_tokens": used,
        "limit_tokens": limit,
        "percentage_used": pct,
        "is_blocked": is_blocked,
        "billing_mode": client.billing_mode,
        "monthly_fee_mxn": client.monthly_fee_mxn,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
    }
