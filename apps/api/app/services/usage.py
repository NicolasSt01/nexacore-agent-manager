import uuid

from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import UsageRecord
from .ai import Completion
from .fx import usd_to_mxn
from .pricing import resolve_price


def record_usage(
    db: Session,
    agency_id: uuid.UUID,
    client_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    provider: str,
    model: str,
    completion: Completion,
    *,
    source: str = "",
) -> None:
    """Store token usage for a completion, with the cost frozen at write time.

    client_id is required: quotas and billing are per client, and the record
    must survive the deletion of the agent that produced it.

    The price and FX rate are snapshotted here rather than recomputed later, so
    a provider raising its price tomorrow cannot rewrite what was earned today.
    Doing it in this one place means no call site can forget it.
    """
    if completion.input_tokens <= 0 and completion.output_tokens <= 0:
        return

    price = resolve_price(db, provider, model)
    cost_usd = price.cost_usd(completion.input_tokens, completion.output_tokens)
    try:
        rate, _ = usd_to_mxn(db)
    except Exception:  # noqa: BLE001 - never let FX break message delivery
        rate = Decimal("0")

    db.add(
        UsageRecord(
            agency_id=agency_id,
            client_id=client_id,
            agent_id=agent_id,
            provider=provider,
            model=model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            source=source,
            input_price_per_1k_usd=price.input_per_1k_usd,
            output_price_per_1k_usd=price.output_per_1k_usd,
            cost_usd=cost_usd,
            usd_to_mxn=rate,
            cost_mxn=cost_usd * rate,
            price_source=price.source,
        )
    )
