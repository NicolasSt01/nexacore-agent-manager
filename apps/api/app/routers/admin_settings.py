"""Superadmin-only global settings: outbound email, model prices, model sync.

These control money and credentials for the whole agency, so every endpoint is
gated on `require_superadmin` — a seller must never reach them.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_superadmin
from ..models import AgencySettings, ModelPrice, User, now_utc
from ..schemas_admin import (
    AgencySettingsOut,
    PoolStatusOut,
    AgencySettingsUpdate,
    ModelPriceCreate,
    ModelPriceOut,
    ModelSyncReportOut,
    TestEmailRequest,
)
from ..security import encrypt_secret
from ..services.mailer import send_test_email
from ..services.model_sync import run_sync, seed_prices_from_catalog
from ..services.pricing import set_price


router = APIRouter(prefix="/admin", tags=["Admin settings"])


def _settings_row(db: Session, agency_id: uuid.UUID) -> AgencySettings:
    row = db.scalar(select(AgencySettings).where(AgencySettings.agency_id == agency_id))
    if not row:
        row = AgencySettings(agency_id=agency_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _settings_out(row: AgencySettings) -> dict:
    return {
        "emails_enabled": row.emails_enabled,
        "smtp_host": row.smtp_host,
        "smtp_port": row.smtp_port,
        "smtp_user": row.smtp_user,
        # The password is never returned; only whether one is stored.
        "has_smtp_password": bool(row.encrypted_smtp_password),
        "smtp_use_tls": row.smtp_use_tls,
        "smtp_from_email": row.smtp_from_email,
        "smtp_from_name": row.smtp_from_name,
        "owner_alert_email": row.owner_alert_email,
        "notify_seller_on_quota": row.notify_seller_on_quota,
        "notify_client_on_quota": row.notify_client_on_quota,
        "pool_degrade_percent": row.pool_degrade_percent,
        "pool_block_percent": row.pool_block_percent,
        "pool_fallback_model": row.pool_fallback_model,
        "pool_alert_percent": row.pool_alert_percent,
        "updated_at": row.updated_at,
    }


@router.get("/settings", response_model=AgencySettingsOut)
def get_settings_endpoint(db: Session = Depends(get_db), user: User = Depends(require_superadmin)):
    return _settings_out(_settings_row(db, user.agency_id))


@router.patch("/settings", response_model=AgencySettingsOut)
def update_settings(
    payload: AgencySettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_superadmin),
):
    row = _settings_row(db, user.agency_id)
    values = payload.model_dump(exclude_unset=True)
    password = values.pop("smtp_password", None)
    if password:
        row.encrypted_smtp_password = encrypt_secret(password)
    for key, value in values.items():
        setattr(row, key, value)
    if row.emails_enabled and (not row.smtp_host or not row.smtp_from_email):
        raise HTTPException(
            status_code=400, detail="Set the SMTP host and the sender address before enabling email"
        )
    row.updated_at = now_utc()
    db.commit()
    db.refresh(row)
    return _settings_out(row)


@router.post("/settings/test-email", status_code=status.HTTP_200_OK)
def test_email(
    payload: TestEmailRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_superadmin),
):
    sent = send_test_email(db, user.agency_id, str(payload.to))
    if not sent:
        raise HTTPException(
            status_code=400,
            detail="The email could not be sent. Check that email is enabled and the SMTP settings are correct.",
        )
    return {"ok": True, "message": f"Test email sent to {payload.to}"}


# --- Model prices ---------------------------------------------------------


@router.get("/model-prices", response_model=list[ModelPriceOut])
def list_prices(db: Session = Depends(get_db), user: User = Depends(require_superadmin)):
    """Every price version, newest first. History is never edited or deleted."""
    return db.scalars(
        select(ModelPrice).order_by(ModelPrice.provider, ModelPrice.model, ModelPrice.effective_from.desc())
    ).all()


@router.post("/model-prices", response_model=ModelPriceOut, status_code=status.HTTP_201_CREATED)
def create_price(
    payload: ModelPriceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_superadmin),
):
    """Add a new price version.

    This is an INSERT, never an UPDATE: usage already recorded keeps the price
    it was charged at, so past margins are not rewritten.
    """
    row = set_price(
        db,
        provider=payload.provider,
        model=payload.model,
        input_per_1k_usd=Decimal(str(payload.input_price_per_1k_usd)),
        output_per_1k_usd=Decimal(str(payload.output_price_per_1k_usd)),
        effective_from=payload.effective_from,
        origin="manual",
        note=payload.note,
        created_by_user_id=user.id,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/model-prices/seed", status_code=status.HTTP_200_OK)
def seed_prices(db: Session = Depends(get_db), user: User = Depends(require_superadmin)):
    """Fill in prices for catalog models that have none. Never overwrites."""
    added = seed_prices_from_catalog(db)
    return {"added": added}


# --- Model sync -----------------------------------------------------------


@router.post("/model-sync/run", response_model=ModelSyncReportOut)
def run_model_sync(db: Session = Depends(get_db), user: User = Depends(require_superadmin)):
    """Run the catalog check now instead of waiting for the daily job."""
    report = run_sync(db, user.agency_id)
    return {
        "checked_providers": report.checked_providers,
        "unreachable": [{"provider": p, "base_url": u} for p, u in report.unreachable],
        "retired": [{"provider": p, "model": m} for p, m in report.retired],
        "new_models": [{"provider": p, "model": m} for p, m in report.new_models],
        "agents_at_risk": [
            {"client_name": c, "agent_name": a, "model": m} for c, a, m in report.agents_at_risk
        ],
        "has_changes": report.has_changes,
    }


# --- Subscription pool ----------------------------------------------------


@router.get("/pool", response_model=list[PoolStatusOut])
def pool_status(db: Session = Depends(get_db), user: User = Depends(require_superadmin)):
    """State of every subscription pool: the shared allowance whose exhaustion
    would stop all clients on that key at once."""
    from ..models import SubscriptionUsage
    from ..services.providers import PROVIDERS, has_shared_pool, resolve_provider_credentials
    from ..services.subscription import get_pool_state, latest_snapshot

    rows = []
    for provider, meta in PROVIDERS.items():
        if not has_shared_pool(provider):
            continue
        configured = resolve_provider_credentials(db, user.agency_id, provider) is not None
        snapshot = latest_snapshot(db, user.agency_id, provider) if configured else None
        state = get_pool_state(db, user.agency_id, provider) if configured else None

        windows = []
        for name, window in ((snapshot.windows if snapshot else None) or {}).items():
            if isinstance(window, dict):
                windows.append({
                    "name": name,
                    "percent": float(window.get("percent") or 0),
                    "status": str(window.get("status") or "ok"),
                    "resets_at": str(window.get("resetsAt") or ""),
                })

        rows.append({
            "provider": provider,
            "label": meta["label"],
            "configured": configured,
            "percent": state.percent if state else 0.0,
            "status": snapshot.status if snapshot else "unknown",
            "degraded": bool(state and state.degraded),
            "blocked": bool(state and state.blocked),
            "windows": windows,
            "captured_at": snapshot.captured_at if snapshot else None,
            "tokens_at_capture": snapshot.tokens_at_capture if snapshot else 0,
            "tokens_per_percent": _tokens_per_percent(db, user.agency_id, provider),
        })
    return rows


def _tokens_per_percent(db: Session, agency_id: uuid.UUID, provider: str) -> float | None:
    """How many of our tokens move the pool one percentage point.

    Derived from the oldest and newest snapshots inside the current window.
    Returns None until there is enough movement to divide by.
    """
    from ..models import SubscriptionUsage

    rows = db.scalars(
        select(SubscriptionUsage)
        .where(SubscriptionUsage.agency_id == agency_id, SubscriptionUsage.provider == provider)
        .order_by(SubscriptionUsage.captured_at.asc())
    ).all()
    if len(rows) < 2:
        return None
    # Only compare readings where the percentage rose: a reset makes it fall,
    # and spanning a reset would give a meaningless number.
    best = None
    for earlier, later in zip(rows, rows[1:]):
        delta_percent = later.percent - earlier.percent
        delta_tokens = later.tokens_at_capture - earlier.tokens_at_capture
        if delta_percent > 0.5 and delta_tokens > 0:
            best = delta_tokens / delta_percent
    return round(best, 1) if best else None


@router.post("/pool/refresh", response_model=list[PoolStatusOut])
def refresh_pool(db: Session = Depends(get_db), user: User = Depends(require_superadmin)):
    """Take a reading now instead of waiting for the daily job."""
    from ..services.subscription import capture_and_alert

    capture_and_alert(db, user.agency_id)
    return pool_status(db, user)
