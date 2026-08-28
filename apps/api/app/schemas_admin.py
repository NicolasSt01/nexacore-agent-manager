import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AgencySettingsUpdate(BaseModel):
    emails_enabled: bool | None = None
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = Field(default=None, max_length=255)
    # Write-only: omitted or blank keeps the stored password.
    smtp_password: str | None = Field(default=None, max_length=255)
    smtp_use_tls: bool | None = None
    smtp_from_email: EmailStr | None = None
    smtp_from_name: str | None = Field(default=None, max_length=180)
    owner_alert_email: EmailStr | None = None
    notify_seller_on_quota: bool | None = None
    notify_client_on_quota: bool | None = None
    pool_degrade_percent: int | None = Field(default=None, ge=1, le=100)
    pool_block_percent: int | None = Field(default=None, ge=1, le=100)
    pool_fallback_model: str | None = Field(default=None, max_length=180)
    pool_alert_percent: int | None = Field(default=None, ge=1, le=100)


class AgencySettingsOut(BaseModel):
    emails_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    has_smtp_password: bool
    smtp_use_tls: bool
    smtp_from_email: str
    smtp_from_name: str
    owner_alert_email: str
    notify_seller_on_quota: bool
    notify_client_on_quota: bool
    pool_degrade_percent: int
    pool_block_percent: int
    pool_fallback_model: str
    pool_alert_percent: int
    updated_at: datetime


class PoolWindow(BaseModel):
    name: str
    percent: float
    status: str
    resets_at: str


class PoolStatusOut(BaseModel):
    provider: str
    label: str
    configured: bool
    percent: float
    status: str
    degraded: bool
    blocked: bool
    windows: list[PoolWindow]
    captured_at: datetime | None
    tokens_at_capture: int
    # Measured capacity: our tokens per percentage point, once there is enough
    # history to compute it. None until then.
    tokens_per_percent: float | None = None


class TestEmailRequest(BaseModel):
    to: EmailStr


class ModelPriceCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=30)
    model: str = Field(min_length=1, max_length=180)
    input_price_per_1k_usd: float = Field(ge=0)
    output_price_per_1k_usd: float = Field(ge=0)
    # Defaults to now; set a past date to backfill a price that was already in
    # force, never to rewrite one that was already charged.
    effective_from: datetime | None = None
    note: str = Field(default="", max_length=500)


class ModelPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    provider: str
    model: str
    input_price_per_1k_usd: float
    output_price_per_1k_usd: float
    effective_from: datetime
    origin: str
    note: str
    created_at: datetime


class ProviderIssue(BaseModel):
    provider: str
    base_url: str


class ModelRef(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str
    model: str


class AgentAtRisk(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    client_name: str
    agent_name: str
    model: str


class ModelSyncReportOut(BaseModel):
    checked_providers: list[str]
    unreachable: list[ProviderIssue]
    retired: list[ModelRef]
    new_models: list[ModelRef]
    agents_at_risk: list[AgentAtRisk]
    has_changes: bool
