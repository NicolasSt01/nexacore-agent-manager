from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_superadmin
from ..models import Agent, Client, Conversation, Message, UsageRecord, User, WhatsAppChannel, now_utc
from ..services import billing as billing_service
from ..schemas import DashboardMetrics, DashboardOut, FinanceDashboardOut


router = APIRouter(prefix="/dashboard", tags=["Inicio"])


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    agency_id = user.agency_id
    clients = db.scalar(select(func.count(Client.id)).where(Client.agency_id == agency_id)) or 0
    active_clients = db.scalar(
        select(func.count(Client.id)).where(Client.agency_id == agency_id, Client.is_active.is_(True))
    ) or 0
    agents = db.scalar(select(func.count(Agent.id)).where(Agent.agency_id == agency_id)) or 0
    active_agents = db.scalar(
        select(func.count(Agent.id)).where(Agent.agency_id == agency_id, Agent.is_active.is_(True))
    ) or 0
    conversations = db.scalar(
        select(func.count(Conversation.id)).where(Conversation.agency_id == agency_id)
    ) or 0
    channels = db.scalar(
        select(func.count(WhatsAppChannel.id)).where(WhatsAppChannel.agency_id == agency_id)
    ) or 0
    connected_channels = db.scalar(
        select(func.count(WhatsAppChannel.id)).where(
            WhatsAppChannel.agency_id == agency_id,
            WhatsAppChannel.status == "connected",
        )
    ) or 0
    recent_agents = db.scalars(
        select(Agent).where(Agent.agency_id == agency_id).order_by(Agent.created_at.desc()).limit(5)
    ).all()
    return {
        "clients": clients,
        "active_clients": active_clients,
        "agents": agents,
        "active_agents": active_agents,
        "conversations": conversations,
        "channels": channels,
        "connected_channels": connected_channels,
        "recent_agents": recent_agents,
    }


@router.get("/metrics", response_model=DashboardMetrics)
def dashboard_metrics(
    days: int = Query(default=14, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agency_id = user.agency_id
    start_date = (now_utc() - timedelta(days=days - 1)).date()
    since = now_utc() - timedelta(days=days)

    messages = db.scalar(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.agency_id == agency_id, Message.created_at >= since)
    ) or 0
    human_conversations = db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.agency_id == agency_id, Conversation.mode == "human", Conversation.created_at >= since
        )
    ) or 0

    channel_rows = db.execute(
        select(Conversation.channel, func.count(Conversation.id))
        .where(Conversation.agency_id == agency_id, Conversation.created_at >= since)
        .group_by(Conversation.channel)
    ).all()
    by_channel = {channel: count for channel, count in channel_rows}

    # New conversations per day over the selected window (zero-filled).
    day = func.date(Conversation.created_at)
    daily_rows = db.execute(
        select(day, func.count(Conversation.id))
        .where(Conversation.agency_id == agency_id, day >= start_date)
        .group_by(day)
    ).all()
    counts = {str(d): c for d, c in daily_rows}
    daily_conversations = [
        {"date": (start_date + timedelta(days=i)).isoformat(), "count": counts.get((start_date + timedelta(days=i)).isoformat(), 0)}
        for i in range(days)
    ]

    top_rows = db.execute(
        select(Agent.id, Agent.name, func.count(Conversation.id))
        .join(Conversation, Conversation.agent_id == Agent.id)
        .where(Agent.agency_id == agency_id, Conversation.created_at >= since)
        .group_by(Agent.id, Agent.name)
        .order_by(func.count(Conversation.id).desc())
        .limit(5)
    ).all()
    top_agents = [{"id": aid, "name": name, "conversations": count} for aid, name, count in top_rows]

    tokens_in, tokens_out = db.execute(
        select(
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
        ).where(UsageRecord.agency_id == agency_id, UsageRecord.created_at >= since)
    ).one()
    usage_rows = db.execute(
        select(
            UsageRecord.model,
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
        )
        .where(UsageRecord.agency_id == agency_id, UsageRecord.created_at >= since)
        .group_by(UsageRecord.model)
        .order_by((func.sum(UsageRecord.input_tokens) + func.sum(UsageRecord.output_tokens)).desc())
        .limit(6)
    ).all()
    usage_by_model = [{"model": model, "input_tokens": input_tokens, "output_tokens": output_tokens} for model, input_tokens, output_tokens in usage_rows]

    return {
        "messages": messages,
        "human_conversations": human_conversations,
        "by_channel": by_channel,
        "daily_conversations": daily_conversations,
        "top_agents": top_agents,
        "tokens_in": int(tokens_in),
        "tokens_out": int(tokens_out),
        "usage_by_model": usage_by_model,
    }


@router.get("/finance", response_model=FinanceDashboardOut)
def finance_dashboard(db: Session = Depends(get_db), user: User = Depends(require_superadmin)):
    """Projected revenue, real AI cost and margin, per seller and per client.

    Revenue is a **projection** of the recurring fees of active clients;
    accounting owns invoicing and payment records, so nothing here claims an
    amount was actually collected.

    Cost is **real and immutable**: it comes from the snapshot frozen onto each
    usage record at the time it was written, never recomputed from today's
    prices. A provider raising its price tomorrow does not rewrite the margin
    earned today.
    """
    agency_id = user.agency_id
    clients = db.scalars(select(Client).where(Client.agency_id == agency_id, Client.is_active.is_(True))).all()

    def revenue(rows) -> Decimal:
        # BYOK clients pay a flat platform fee too, so every billing mode counts.
        return sum((row.monthly_fee_mxn for row in rows), Decimal("0"))

    # Tokens and frozen cost per client, in one grouped query.
    usage_rows = db.execute(
        select(
            UsageRecord.client_id,
            func.coalesce(func.sum(UsageRecord.input_tokens + UsageRecord.output_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cost_mxn), 0),
        )
        .where(UsageRecord.agency_id == agency_id)
        .group_by(UsageRecord.client_id)
    ).all()
    tokens_by_client = {row[0]: int(row[1]) for row in usage_rows}
    cost_by_client = {row[0]: Decimal(str(row[2] or 0)) for row in usage_rows}

    # Usage we could not price is reported, not silently counted as free: a
    # zero that looks like margin is how the numbers quietly go wrong.
    unpriced = db.scalar(
        select(func.count(UsageRecord.id)).where(
            UsageRecord.agency_id == agency_id, UsageRecord.price_source == "unknown"
        )
    ) or 0

    def cost(rows) -> Decimal:
        return sum((cost_by_client.get(row.id, Decimal("0")) for row in rows), Decimal("0"))

    workers = db.scalars(select(User).where(User.agency_id == agency_id).order_by(User.created_at.asc())).all()
    workers_metrics = []
    for worker in workers:
        owned = [client for client in clients if client.created_by_user_id == worker.id]
        worker_revenue = revenue(owned)
        worker_cost = cost(owned)
        workers_metrics.append({
            "worker_id": worker.id,
            "worker_name": worker.name,
            "worker_email": worker.email,
            "clients_count": len(owned),
            "monthly_revenue_mxn": float(worker_revenue),
            "ai_cost_mxn": float(worker_cost),
            "margin_mxn": float(worker_revenue - worker_cost),
            "tokens_consumed": sum(tokens_by_client.get(client.id, 0) for client in owned),
        })

    seller_names = {worker.id: worker.name for worker in workers}
    clients_metrics = []
    for client in clients:
        quota = billing_service.get_quota_status(db, client)
        client_cost = cost_by_client.get(client.id, Decimal("0"))
        clients_metrics.append({
            "client_id": client.id,
            "client_name": client.name,
            "seller_name": seller_names.get(client.created_by_user_id, ""),
            "billing_mode": client.billing_mode,
            "monthly_fee_mxn": float(client.monthly_fee_mxn),
            "ai_cost_mxn": float(client_cost),
            "margin_mxn": float(client.monthly_fee_mxn - client_cost),
            "tokens_used": quota["used_tokens"],
            "monthly_token_limit": quota["limit_tokens"],
            "usage_pct": quota["percentage_used"],
            "is_blocked": quota["is_blocked"],
        })
    clients_metrics.sort(key=lambda row: row["ai_cost_mxn"], reverse=True)

    total_revenue = revenue(clients)
    total_cost = cost(clients)
    margin_pct = float((total_revenue - total_cost) / total_revenue * 100) if total_revenue else 0.0

    return {
        "total_clients": len(clients),
        "total_monthly_revenue_mxn": float(total_revenue),
        "total_ai_cost_mxn": float(total_cost),
        "total_margin_mxn": float(total_revenue - total_cost),
        "margin_pct": round(margin_pct, 1),
        "total_tokens_consumed": sum(tokens_by_client.values()),
        "unpriced_usage_records": int(unpriced),
        "workers_metrics": workers_metrics,
        "clients_metrics": clients_metrics,
    }
