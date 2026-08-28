"""Background daily jobs.

A plain asyncio loop rather than a scheduler dependency: there is exactly one
daily job, and adding Celery or APScheduler for it would mean a broker and a
second process to operate.

Note this runs per API process. With more than one replica the job would run
more than once a day; the work is idempotent (the FX row is unique per day, the
price seed only fills gaps) but the owner would get duplicate emails. Set
DAILY_JOBS_ENABLED=false on all but one replica when scaling out.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from ..config import get_settings
from ..database import SessionLocal


logger = logging.getLogger("nexacore.scheduler")

# Early morning Mexico City time: the report is waiting when the day starts.
RUN_AT_UTC = time(hour=13, minute=0)


def _seconds_until_next_run() -> float:
    now = datetime.now(timezone.utc)
    target = datetime.combine(now.date(), RUN_AT_UTC, tzinfo=timezone.utc)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_daily_jobs() -> None:
    """Refresh FX, report model-catalog drift, snapshot subscription pools."""
    from .fx import usd_to_mxn
    from .model_sync import sync_all_agencies
    from .subscription import capture_all_agencies

    db = SessionLocal()
    try:
        rate, source = usd_to_mxn(db)
        logger.info("Daily FX refresh: USD/MXN = %s (%s)", rate, source)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Daily FX refresh failed: %s", exc)
    finally:
        db.close()

    db = SessionLocal()
    try:
        sync_all_agencies(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Daily model sync failed: %s", exc)
    finally:
        db.close()

    db = SessionLocal()
    try:
        capture_all_agencies(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Daily subscription pool capture failed: %s", exc)
    finally:
        db.close()


async def daily_jobs_loop() -> None:
    """Sleep until the run time, work, repeat. Cancelled on shutdown."""
    while True:
        try:
            await asyncio.sleep(_seconds_until_next_run())
        except asyncio.CancelledError:
            raise
        try:
            # The jobs are blocking (httpx sync + SQLAlchemy), so keep them off
            # the event loop or they stall every request while they run.
            await asyncio.to_thread(run_daily_jobs)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop must survive anything
            logger.warning("Daily jobs raised: %s", exc)


def enabled() -> bool:
    return bool(getattr(get_settings(), "daily_jobs_enabled", True))
