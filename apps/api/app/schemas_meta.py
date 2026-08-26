import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MetaChannelUpdate(BaseModel):
    agent_id: uuid.UUID
    # Page id for Messenger, Instagram user id for Instagram.
    account_id: str | None = Field(default=None, max_length=80)
    # Secrets are write-only: omitted or blank values keep the stored ones.
    access_token: str | None = Field(default=None, max_length=4000)
    app_secret: str | None = Field(default=None, max_length=255)


class MetaChannelOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    agent_id: uuid.UUID
    platform: str
    status: str
    account_id: str
    account_name: str | None
    has_access_token: bool
    has_app_secret: bool
    webhook_url: str
    webhook_verify_token: str
    last_error: str | None
    is_enabled: bool
    last_connected_at: datetime | None
    created_at: datetime
    updated_at: datetime
