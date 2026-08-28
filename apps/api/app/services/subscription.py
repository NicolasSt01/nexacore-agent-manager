"""Shared subscription pool: monitoring and circuit breaker.

Subscription gateways meter one allowance shared by every client on the key.
Running it dry takes the whole portfolio down at once — not one client over
their plan, but every client at the same time, none of them at fault.

So this module does two things:

1. **Watches** the pool and keeps snapshots, so we learn the real capacity
   (how many of our tokens move the percentage how much).
2. **Degrades in order** rather than failing all at once: past the degrade
   threshold agents switch to a model that does not consume the pool; past the
   block threshold they hand over to a human.

The check sits on the hot path, so the reading is cached in the database and
refreshed at most every `REFRESH_MINUTES`.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AgencySettings, SubscriptionUsage, UsageRecord, now_utc
from .history import aware
from .providers import PROVIDERS, has_shared_pool, resolve_provider_credentials


logger = logging.getLogger("nexacore.subscription")

USAGE_TIMEOUT = 10
# How stale a reading may be before the hot path refreshes it. Short enough to
# catch a burst, long enough not to call the provider on every message.
REFRESH_MINUTES = 5

DEFAULT_DEGRADE_PERCENT = 80
DEFAULT_BLOCK_PERCENT = 95
DEFAULT_ALERT_PERCENT = 70


@dataclass(frozen=True)
class PoolState:
    provider: str
    percent: float
    degraded: bool
    blocked: bool
    fallback_model: str
    stale: bool = False

    @property
    def ok(self) -> bool:
        return not self.degraded and not self.blocked


OK_STATE = PoolState(provider="", percent=0.0, degraded=False, blocked=False, fallback_model="")


def fetch_usage(base_url: str, api_key: str) -> dict | None:
    """Raw pool reading from the provider, or None if unavailable."""
    url = f"{base_url.rstrip('/')}/usage"
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=USAGE_TIMEOUT)
        if response.status_code >= 400:
            return None
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    return usage if isinstance(usage, dict) else None


def _worst_window(usage: dict) -> tuple[float, str]:
    """The highest percentage across windows — the one that will stop us first."""
    percent = 0.0
    status = "ok"
    for window in usage.values():
        if not isinstance(window, dict):
            continue
        value = window.get("percent")
        if isinstance(value, (int, float)):
            percent = max(percent, float(value))
        if window.get("status") and window["status"] != "ok":
            status = str(window["status"])
    return percent, status


def capture(db: Session, agency_id: uuid.UUID, provider: str) -> SubscriptionUsage | None:
    """Read the pool now and store a snapshot. Returns None if unavailable."""
    if not has_shared_pool(provider):
        return None
    credentials = resolve_provider_credentials(db, agency_id, provider)
    if not credentials:
        return None
    base_url, api_key = credentials
    usage = fetch_usage(base_url, api_key)
    if usage is None:
        return None

    percent, status = _worst_window(usage)
    tokens = db.scalar(
        select(func.coalesce(func.sum(UsageRecord.input_tokens + UsageRecord.output_tokens), 0)).where(
            UsageRecord.agency_id == agency_id, UsageRecord.provider == provider
        )
    ) or 0
    snapshot = SubscriptionUsage(
        agency_id=agency_id,
        provider=provider,
        percent=percent,
        windows=usage,
        status=status,
        tokens_at_capture=int(tokens),
    )
    db.add(snapshot)
    db.commit()
    return snapshot


def latest_snapshot(db: Session, agency_id: uuid.UUID, provider: str) -> SubscriptionUsage | None:
    return db.scalar(
        select(SubscriptionUsage)
        .where(SubscriptionUsage.agency_id == agency_id, SubscriptionUsage.provider == provider)
        .order_by(SubscriptionUsage.captured_at.desc())
        .limit(1)
    )


def _thresholds(db: Session, agency_id: uuid.UUID) -> tuple[int, int, str]:
    row = db.scalar(select(AgencySettings).where(AgencySettings.agency_id == agency_id))
    if not row:
        return DEFAULT_DEGRADE_PERCENT, DEFAULT_BLOCK_PERCENT, ""
    return row.pool_degrade_percent, row.pool_block_percent, row.pool_fallback_model


def get_pool_state(db: Session, agency_id: uuid.UUID, provider: str) -> PoolState:
    """Current pool pressure, refreshed at most every REFRESH_MINUTES.

    Never raises and never blocks on a provider outage: if the pool cannot be
    read, the last snapshot is used, and if there is none we assume OK. Failing
    open is deliberate — a monitoring glitch must not stop customer replies.
    """
    if not has_shared_pool(provider):
        return OK_STATE

    snapshot = latest_snapshot(db, agency_id, provider)
    stale = False
    if snapshot is None:
        snapshot = capture(db, agency_id, provider)
    elif now_utc() - aware(snapshot.captured_at) > timedelta(minutes=REFRESH_MINUTES):
        refreshed = capture(db, agency_id, provider)
        if refreshed is None:
            stale = True  # provider unreachable: keep using the last reading
        else:
            snapshot = refreshed

    if snapshot is None:
        return OK_STATE

    degrade_at, block_at, fallback = _thresholds(db, agency_id)
    return PoolState(
        provider=provider,
        percent=snapshot.percent,
        degraded=snapshot.percent >= degrade_at,
        blocked=snapshot.percent >= block_at,
        fallback_model=fallback,
        stale=stale,
    )


def resolve_model(state: PoolState, agent_model: str) -> tuple[str, bool]:
    """(model to use, whether it was swapped).

    Under pressure we keep answering on a model that does not consume the pool,
    rather than going silent for every client at once.
    """
    if state.degraded and not state.blocked and state.fallback_model.strip():
        return state.fallback_model.strip(), True
    return agent_model, False


def capture_and_alert(db: Session, agency_id: uuid.UUID) -> list[SubscriptionUsage]:
    """Snapshot every pooled provider for one agency and alert the owner once
    per crossing. Used by the daily job."""
    from .notifications import notify_pool_pressure

    row = db.scalar(select(AgencySettings).where(AgencySettings.agency_id == agency_id))
    alert_at = row.pool_alert_percent if row else DEFAULT_ALERT_PERCENT

    snapshots = []
    for provider in [name for name in PROVIDERS if has_shared_pool(name)]:
        snapshot = capture(db, agency_id, provider)
        if snapshot is None:
            continue
        snapshots.append(snapshot)
        if snapshot.percent < alert_at:
            # Back below the line: re-arm so the next crossing alerts again.
            if row and row.pool_alerted_at:
                row.pool_alerted_at = None
                db.commit()
            continue
        # Alert once per crossing, not on every reading above the line.
        if row and row.pool_alerted_at:
            continue
        notify_pool_pressure(db, agency_id, provider, snapshot.percent, snapshot.windows)
        if row:
            row.pool_alerted_at = now_utc()
            db.commit()
    return snapshots


def capture_all_agencies(db: Session) -> None:
    """Entry point for the daily scheduler."""
    from ..models import Agency

    for agency_id in db.scalars(select(Agency.id)):
        try:
            capture_and_alert(db, agency_id)
        except Exception as exc:  # noqa: BLE001 - one agency must not stop the rest
            logger.warning("Pool capture failed for agency %s: %s", agency_id, exc)
