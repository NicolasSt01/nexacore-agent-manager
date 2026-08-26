"""Management endpoints for the Messenger and Instagram channels.

One router serves both platforms; the platform is a path segment and is
validated against the supported set. Scoped like every client-owned resource:
a seller only reaches clients in their own portfolio.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, is_superadmin
from ..models import Agent, Client, MetaMessagingChannel, User, new_public_id, now_utc
from ..schemas_meta import MetaChannelOut, MetaChannelUpdate
from ..security import decrypt_secret, encrypt_secret
from ..services.meta_messaging import PLATFORMS, verify_account


router = APIRouter(prefix="/meta", tags=["Messenger/Instagram"])


def _require_platform(platform: str) -> str:
    if platform not in PLATFORMS:
        raise HTTPException(status_code=404, detail="Unknown platform")
    return platform


def _client_for_user(db: Session, user: User, client_id: uuid.UUID) -> Client:
    stmt = select(Client).where(Client.id == client_id, Client.agency_id == user.agency_id)
    if not is_superadmin(user):
        stmt = stmt.where(Client.created_by_user_id == user.id)
    client = db.scalar(stmt)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def _channel_for_user(db: Session, user: User, client_id: uuid.UUID, platform: str) -> MetaMessagingChannel:
    client = _client_for_user(db, user, client_id)
    channel = db.scalar(
        select(MetaMessagingChannel).where(
            MetaMessagingChannel.client_id == client.id,
            MetaMessagingChannel.platform == platform,
        )
    )
    if not channel:
        raise HTTPException(status_code=404, detail="This client does not have that channel configured yet")
    return channel


def _public_channel(channel: MetaMessagingChannel) -> dict:
    webhook_url = f"{get_settings().frontend_url.rstrip('/')}/api/public/meta/channels/{channel.id}/webhook"
    return {
        "id": channel.id,
        "client_id": channel.client_id,
        "agent_id": channel.agent_id,
        "platform": channel.platform,
        "status": channel.status,
        "account_id": channel.account_id,
        "account_name": channel.account_name,
        "has_access_token": bool(channel.encrypted_access_token),
        "has_app_secret": bool(channel.encrypted_app_secret),
        "webhook_url": webhook_url,
        "webhook_verify_token": channel.webhook_verify_token,
        "last_error": channel.last_error,
        "is_enabled": channel.is_enabled,
        "last_connected_at": channel.last_connected_at,
        "created_at": channel.created_at,
        "updated_at": channel.updated_at,
    }


@router.get("/{platform}/channels/{client_id}", response_model=MetaChannelOut)
def get_channel(
    platform: str,
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _public_channel(_channel_for_user(db, user, client_id, _require_platform(platform)))


@router.put("/{platform}/channels/{client_id}", response_model=MetaChannelOut)
def configure_channel(
    platform: str,
    client_id: uuid.UUID,
    payload: MetaChannelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_platform(platform)
    client = _client_for_user(db, user, client_id)
    agent = db.scalar(
        select(Agent).where(
            Agent.id == payload.agent_id,
            Agent.client_id == client.id,
            Agent.agency_id == user.agency_id,
        )
    )
    if not agent:
        raise HTTPException(status_code=400, detail="Select an agent that belongs to this client")
    channel = db.scalar(
        select(MetaMessagingChannel).where(
            MetaMessagingChannel.client_id == client.id,
            MetaMessagingChannel.platform == platform,
        )
    )
    if not channel:
        channel = MetaMessagingChannel(
            agency_id=user.agency_id,
            client_id=client.id,
            agent_id=agent.id,
            platform=platform,
            webhook_verify_token=new_public_id(),
        )
        db.add(channel)
    channel.agent_id = agent.id
    channel.is_enabled = True
    if payload.account_id is not None:
        channel.account_id = payload.account_id.strip()
    # Blank secrets keep the stored values, so the form can resubmit safely.
    if payload.access_token:
        channel.encrypted_access_token = encrypt_secret(payload.access_token.strip())
    if payload.app_secret:
        channel.encrypted_app_secret = encrypt_secret(payload.app_secret.strip())
    channel.updated_at = now_utc()
    db.commit()
    db.refresh(channel)
    return _public_channel(channel)


@router.post("/{platform}/channels/{client_id}/connect", response_model=MetaChannelOut)
async def connect_channel(
    platform: str,
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    channel = _channel_for_user(db, user, client_id, _require_platform(platform))
    if not channel.encrypted_access_token or not channel.encrypted_app_secret or not channel.account_id:
        raise HTTPException(
            status_code=400,
            detail="Save the account ID, access token and app secret before connecting",
        )
    try:
        profile = await verify_account(
            decrypt_secret(channel.encrypted_access_token), channel.platform, channel.account_id
        )
    except HTTPException as exc:
        channel.status = "error"
        channel.last_error = str(exc.detail)
        channel.updated_at = now_utc()
        db.commit()
        db.refresh(channel)
        return _public_channel(channel)
    channel.status = "connected"
    channel.account_name = profile.get("name") or profile.get("username")
    channel.last_error = None
    channel.is_enabled = True
    channel.last_connected_at = now_utc()
    channel.updated_at = now_utc()
    db.commit()
    db.refresh(channel)
    return _public_channel(channel)


@router.post("/{platform}/channels/{client_id}/disconnect", response_model=MetaChannelOut)
def disconnect_channel(
    platform: str,
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    channel = _channel_for_user(db, user, client_id, _require_platform(platform))
    channel.status = "disconnected"
    channel.is_enabled = False
    channel.last_error = None
    channel.updated_at = now_utc()
    db.commit()
    db.refresh(channel)
    return _public_channel(channel)
