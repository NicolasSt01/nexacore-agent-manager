"""USD -> MXN reference rate, from Banco de México's FIX series.

Providers bill in USD and NexaCore charges in MXN, so every cost figure needs a
rate. The rate is fetched once a day and cached; the value applied is
snapshotted onto each usage record, so a later rate move does not rewrite past
margins.

Swapping Banxico for a specific bank later is a change to `_fetch_remote` only.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import FxRate, now_utc


logger = logging.getLogger("nexacore.fx")

BANXICO_FIX_SERIES = "SF43718"
BANXICO_TIMEOUT = 20


def _fetch_remote(on: date) -> Decimal | None:
    """Latest published FIX rate at or before `on`, or None if unavailable.

    Weekends and Mexican bank holidays have no publication, so we ask for a
    window and take the last value rather than a single day.
    """
    settings = get_settings()
    token = (getattr(settings, "banxico_token", "") or "").strip()
    if not token:
        return None
    start = (on - timedelta(days=10)).isoformat()
    url = (
        f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{BANXICO_FIX_SERIES}"
        f"/datos/{start}/{on.isoformat()}"
    )
    try:
        response = httpx.get(url, headers={"Bmx-Token": token}, timeout=BANXICO_TIMEOUT)
        if response.status_code >= 400:
            logger.warning("Banxico returned status %s", response.status_code)
            return None
        series = response.json()["bmx"]["series"][0].get("datos") or []
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.warning("Could not read the Banxico FIX series: %s", exc)
        return None
    for entry in reversed(series):
        raw = (entry.get("dato") or "").replace(",", "")
        try:
            value = Decimal(raw)
        except (ArithmeticError, ValueError):
            continue
        if value > 0:
            return value
    return None


def usd_to_mxn(db: Session, on: date | None = None) -> tuple[Decimal, str]:
    """(rate, source) for the given day, fetching and caching once per day.

    Never raises: an FX outage must not stop the product. It falls back to the
    most recent stored rate, then to the configured seed value.
    """
    on = on or now_utc().date()
    cached = db.scalar(select(FxRate).where(FxRate.base == "USD", FxRate.quote == "MXN", FxRate.rate_date == on))
    if cached:
        return cached.rate, cached.source

    remote = _fetch_remote(on)
    if remote is not None:
        row = FxRate(base="USD", quote="MXN", rate=remote, rate_date=on, source="banxico_fix")
        db.add(row)
        db.commit()
        return remote, "banxico_fix"

    latest = db.scalar(
        select(FxRate)
        .where(FxRate.base == "USD", FxRate.quote == "MXN")
        .order_by(FxRate.rate_date.desc())
        .limit(1)
    )
    if latest:
        # Carry the last published rate forward. Correct behaviour on weekends
        # and holidays, and the safe degradation when Banxico is unreachable.
        return latest.rate, f"{latest.source}:carried"

    fallback = Decimal(str(getattr(get_settings(), "fx_fallback_usd_mxn", 0) or 0))
    return fallback, "fallback"
