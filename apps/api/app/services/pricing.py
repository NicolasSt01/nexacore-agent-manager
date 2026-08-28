"""Model price resolution.

Prices are versioned: a change is an INSERT with a later `effective_from`,
never an UPDATE. Resolution always asks "what was the price at time T", so a
price raised tomorrow leaves yesterday's margin untouched.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ModelPrice, now_utc
from .model_catalog import get_model


# Where a price came from, worst to best.
SOURCE_TABLE = "table"
SOURCE_CATALOG = "catalog"
SOURCE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class PriceSnapshot:
    input_per_1k_usd: Decimal
    output_per_1k_usd: Decimal
    source: str

    def cost_usd(self, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            self.input_per_1k_usd * Decimal(input_tokens) + self.output_per_1k_usd * Decimal(output_tokens)
        ) / Decimal(1000)


UNKNOWN = PriceSnapshot(Decimal("0"), Decimal("0"), SOURCE_UNKNOWN)


def resolve_price(db: Session, provider: str, model: str, at: datetime | None = None) -> PriceSnapshot:
    """Price in force for (provider, model) at `at`.

    Falls back to the static catalog, then to zero. An unknown price never
    blocks a reply — it is recorded as `unknown` and surfaced in the finance
    view, because a silent zero is how margin reporting quietly goes wrong.
    """
    at = at or now_utc()
    row = db.scalar(
        select(ModelPrice)
        .where(ModelPrice.provider == provider, ModelPrice.model == model, ModelPrice.effective_from <= at)
        .order_by(ModelPrice.effective_from.desc())
        .limit(1)
    )
    if row:
        return PriceSnapshot(row.input_price_per_1k_usd, row.output_price_per_1k_usd, SOURCE_TABLE)

    catalog = get_model(model)
    if catalog and catalog.provider == provider:
        return PriceSnapshot(
            Decimal(str(catalog.input_price_per_1k)),
            Decimal(str(catalog.output_price_per_1k)),
            SOURCE_CATALOG,
        )
    return UNKNOWN


def set_price(
    db: Session,
    *,
    provider: str,
    model: str,
    input_per_1k_usd: Decimal,
    output_per_1k_usd: Decimal,
    effective_from: datetime | None = None,
    origin: str = "manual",
    note: str = "",
    created_by_user_id: uuid.UUID | None = None,
) -> ModelPrice:
    """Add a new price version. Never updates an existing row — that is the
    whole point. The caller owns the commit."""
    row = ModelPrice(
        provider=provider,
        model=model,
        input_price_per_1k_usd=input_per_1k_usd,
        output_price_per_1k_usd=output_per_1k_usd,
        effective_from=effective_from or now_utc(),
        origin=origin,
        note=note,
        created_by_user_id=created_by_user_id,
    )
    db.add(row)
    return row


def current_prices(db: Session, at: datetime | None = None) -> dict[tuple[str, str], PriceSnapshot]:
    """The price in force for every (provider, model) that has one."""
    at = at or now_utc()
    rows = db.scalars(
        select(ModelPrice).where(ModelPrice.effective_from <= at).order_by(ModelPrice.effective_from.asc())
    ).all()
    # Ascending order means the last write per key wins, i.e. the latest
    # effective price.
    return {
        (row.provider, row.model): PriceSnapshot(
            row.input_price_per_1k_usd, row.output_price_per_1k_usd, SOURCE_TABLE
        )
        for row in rows
    }
