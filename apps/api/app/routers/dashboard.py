from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_superadmin
from ..models import Agent, Client, Conversation, Message, UsageRecord, User, WhatsAppChannel, now_utc
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
    """Projected revenue per seller and per agency.

    Revenue is a projection of the recurring fees of active clients; NexaCore's
    accounting team owns invoicing and payment records, so nothing here claims
    an amount was actually collected.
    """
    agency_id = user.agency_id
    clients = db.scalars(select(Client).where(Client.agency_id == agency_id, Client.is_active.is_(True))).all()

    def revenue(rows) -> Decimal:
        # BYOK clients pay a flat platform fee too, so every billing mode counts.
        return sum((row.monthly_fee_mxn for row in rows), Decimal("0"))

    # Tokens per client, in one grouped query rather than one query per seller.
    tokens_by_client = dict(
        db.execute(
            select(
                UsageRecord.client_id,
                func.coalesce(func.sum(UsageRecord.input_tokens + UsageRecord.output_tokens), 0),
            )
            .where(UsageRecord.agency_id == agency_id)
            .group_by(UsageRecord.client_id)
        ).all()
    )

    workers = db.scalars(select(User).where(User.agency_id == agency_id).order_by(User.created_at.asc())).all()
    workers_metrics = []
    for worker in workers:
        owned = [client for client in clients if client.created_by_user_id == worker.id]
        workers_metrics.append({
            "worker_id": worker.id,
            "worker_name": worker.name,
            "worker_email": worker.email,
            "clients_count": len(owned),
            "monthly_revenue_mxn": float(revenue(owned)),
            "tokens_consumed": sum(int(tokens_by_client.get(client.id, 0)) for client in owned),
        })

    return {
        "total_clients": len(clients),
        "total_monthly_revenue_mxn": float(revenue(clients)),
        "total_tokens_consumed": sum(int(value) for value in tokens_by_client.values()),
        "workers_metrics": workers_metrics,
    }
