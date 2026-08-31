import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .services.providers import SUPPORTED


# Built from the supported provider registry so adding a provider in one place
# is enough; a hard-coded pattern silently rejects every new one.
PROVIDER_PATTERN = rf"^({'|'.join(SUPPORTED)})$"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    agency_name: str = Field(min_length=2, max_length=180)
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AgencyOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    brand_color: str
    logo_url: str | None = None


class AgencyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    slug: str | None = Field(default=None, min_length=2, max_length=180)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class UserOut(ORMModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    agency: AgencyOut


class ClientBase(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    industry: str = Field(default="", max_length=160)
    description: str = ""
    general_context: str = ""
    is_active: bool = True
    billing_mode: str = Field(default="plan", pattern=r"^(plan|pay_as_you_go|byok)$")
    monthly_fee_mxn: Decimal = Field(default=Decimal("200.00"), ge=0, max_digits=10, decimal_places=2)
    monthly_token_limit: int = Field(default=500000, ge=0)


class ClientCreate(ClientBase):
    # created_by_user_id is deliberately NOT accepted from the request: it is
    # the portfolio isolation key, and a seller must not be able to attribute a
    # client to somebody else. It is always taken from the session.
    pass


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    industry: str | None = None
    description: str | None = None
    general_context: str | None = None
    is_active: bool | None = None
    # Reassigning a client to another seller is a superadmin action; see the
    # dedicated endpoint in routers/clients.py rather than a generic PATCH.
    billing_mode: str | None = Field(default=None, pattern=r"^(plan|pay_as_you_go|byok)$")
    monthly_fee_mxn: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    monthly_token_limit: int | None = Field(default=None, ge=0)


class ClientPortalUpdate(BaseModel):
    portal_enabled: bool | None = None
    portal_slug: str | None = Field(default=None, min_length=2, max_length=180)
    portal_title: str | None = Field(default=None, max_length=180)
    portal_email: EmailStr | None = None
    portal_password: str | None = Field(default=None, min_length=8, max_length=128)


class AgentSummary(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    is_active: bool


class ClientOut(ORMModel):
    id: uuid.UUID
    name: str
    industry: str
    description: str
    general_context: str
    is_active: bool
    portal_slug: str
    portal_enabled: bool
    portal_title: str
    portal_email: EmailStr | None
    portal_password_configured: bool
    portal_domain: str | None
    portal_domain_verified: bool
    created_by_user_id: uuid.UUID | None = None
    billing_mode: str = "plan"
    monthly_fee_mxn: Decimal = Decimal("200.00")
    monthly_token_limit: int = 500000
    billing_anchor_day: int = 1
    # Derived per request from usage_records over the current cycle window;
    # not stored on the client. See services/billing.get_quota_status.
    used_tokens_current_cycle: int = 0
    percentage_tokens_used: float = 0.0
    is_blocked: bool = False
    cycle_start: datetime | None = None
    cycle_end: datetime | None = None
    created_at: datetime
    updated_at: datetime
    agents: list[AgentSummary] = []


class ClientEmailUpdate(BaseModel):
    """Partial update of a client's email settings.

    Sent both by the agency panel and by the client from their own portal, so
    it carries no field either side must not touch.
    """

    notification_email: EmailStr | None = None
    smtp_enabled: bool | None = None
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = Field(default=None, max_length=255)
    # Write-only: the API never returns it, and a blank value keeps the stored one.
    smtp_password: str | None = Field(default=None, max_length=255)
    smtp_use_tls: bool | None = None
    smtp_from_email: EmailStr | None = None
    smtp_from_name: str | None = Field(default=None, max_length=180)


class ClientEmailOut(BaseModel):
    notification_email: str | None
    smtp_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    has_smtp_password: bool
    smtp_use_tls: bool
    smtp_from_email: str
    smtp_from_name: str
    smtp_verified_at: datetime | None
    # True when this client's mail leaves from their own server; otherwise it
    # falls back to the agency's.
    using_own_smtp: bool
    # Whether anything can be delivered at all right now, either way.
    delivery_ready: bool
    alert_email: str | None


class ClientTestEmailRequest(BaseModel):
    to: EmailStr


class ClientDomainSet(BaseModel):
    domain: str = Field(
        min_length=3,
        max_length=255,
        pattern=r"^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$",
    )


class ClientDomainOut(BaseModel):
    domain: str | None
    verified: bool
    txt_host: str | None
    txt_value: str | None


class ProviderKeyUpdate(BaseModel):
    api_key: str = Field(min_length=1)
    base_url: str | None = None


class ProviderOut(BaseModel):
    provider: str
    label: str
    configured: bool
    api_key_masked: str = ""
    base_url: str | None = None


class AgencyUserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="seller", pattern=r"^(seller|superadmin)$")


class AgencyUserOut(ORMModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    created_at: datetime


class ClientOwnerUpdate(BaseModel):
    owner_user_id: uuid.UUID


class WorkerMetrics(BaseModel):
    worker_id: uuid.UUID
    worker_name: str
    worker_email: str
    clients_count: int
    monthly_revenue_mxn: float
    ai_cost_mxn: float
    margin_mxn: float
    tokens_consumed: int


class ClientFinanceMetrics(BaseModel):
    client_id: uuid.UUID
    client_name: str
    seller_name: str
    billing_mode: str
    monthly_fee_mxn: float
    ai_cost_mxn: float
    margin_mxn: float
    tokens_used: int
    monthly_token_limit: int
    usage_pct: float
    is_blocked: bool


class FinanceDashboardOut(BaseModel):
    total_clients: int
    total_monthly_revenue_mxn: float
    # Real, from the immutable cost snapshot on each usage record.
    total_ai_cost_mxn: float
    total_margin_mxn: float
    margin_pct: float
    total_tokens_consumed: int
    # Usage that could not be priced; surfaced so it gets fixed rather than
    # silently inflating the margin.
    unpriced_usage_records: int
    workers_metrics: list[WorkerMetrics]
    clients_metrics: list[ClientFinanceMetrics]


class AgentBase(BaseModel):
    client_id: uuid.UUID
    name: str = Field(min_length=1, max_length=180)
    description: str = ""
    instructions: str = ""
    personality: str = ""
    brief_summary: str = ""
    brief_products: str = ""
    brief_audience: str = ""
    brief_policies: str = ""
    brief_goal: str = ""
    brief_dos: str = ""
    brief_donts: str = ""
    model: str = ""
    provider: str = Field(default="openai", pattern=PROVIDER_PATTERN)
    timezone: str = Field(default="UTC", max_length=64)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=32000)
    memory_limit: int = Field(default=20, ge=0, le=200)
    session_gap_hours: int = Field(default=6, ge=0, le=168)
    history_max_age_days: int = Field(default=7, ge=0, le=365)
    reply_delay_seconds: int = Field(default=8, ge=0, le=120)
    image_enabled: bool = False
    image_model: str = Field(default="", max_length=180)
    audio_enabled: bool = False
    audio_model: str = Field(default="whisper-1", max_length=180)
    widget_enabled: bool = False
    widget_greeting: str = Field(default="", max_length=2000)
    widget_color: str = Field(default="", max_length=20)
    widget_position: str = Field(default="right", pattern=r"^(right|left)$")
    scheduling_enabled: bool = False
    scheduling_owner_email: str = Field(default="", max_length=320)
    scheduling_location: str = Field(default="", max_length=255)
    scheduling_duration_minutes: int = Field(default=60, ge=5, le=720)
    scheduling_hours: str = Field(default="", max_length=2000)
    scheduling_require_email: bool = True
    is_template: bool = False
    template_label: str = Field(default="", max_length=180)
    is_active: bool = True


class AgentCreate(AgentBase):
    pass


class AgentCloneRequest(BaseModel):
    """Clone an existing agent onto another client."""
    client_id: uuid.UUID
    name: str = Field(min_length=1, max_length=180)
    # Knowledge documents are copied with their pre-computed embeddings, so
    # this is cheap; turn it off when the new client's material differs.
    copy_documents: bool = True


class AgentTemplateOut(BaseModel):
    """Summary of a shared template, for the agency-wide library."""
    id: uuid.UUID
    name: str
    template_label: str
    description: str
    industry: str
    source_client_name: str
    provider: str
    model: str
    qa_count: int
    document_count: int
    tool_count: int
    updated_at: datetime


class AgentUpdate(BaseModel):
    client_id: uuid.UUID | None = None
    is_template: bool | None = None
    template_label: str | None = Field(default=None, max_length=180)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    instructions: str | None = None
    personality: str | None = None
    brief_summary: str | None = None
    brief_products: str | None = None
    brief_audience: str | None = None
    brief_policies: str | None = None
    brief_goal: str | None = None
    brief_dos: str | None = None
    brief_donts: str | None = None
    model: str | None = None
    provider: str | None = Field(default=None, pattern=PROVIDER_PATTERN)
    timezone: str | None = Field(default=None, max_length=64)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    memory_limit: int | None = Field(default=None, ge=0, le=200)
    session_gap_hours: int | None = Field(default=None, ge=0, le=168)
    history_max_age_days: int | None = Field(default=None, ge=0, le=365)
    reply_delay_seconds: int | None = Field(default=None, ge=0, le=120)
    image_enabled: bool | None = None
    image_model: str | None = Field(default=None, max_length=180)
    audio_enabled: bool | None = None
    audio_model: str | None = Field(default=None, max_length=180)
    widget_enabled: bool | None = None
    widget_greeting: str | None = Field(default=None, max_length=2000)
    widget_color: str | None = Field(default=None, max_length=20)
    widget_position: str | None = Field(default=None, pattern=r"^(right|left)$")
    scheduling_enabled: bool | None = None
    scheduling_owner_email: str | None = Field(default=None, max_length=320)
    scheduling_location: str | None = Field(default=None, max_length=255)
    scheduling_duration_minutes: int | None = Field(default=None, ge=5, le=720)
    scheduling_hours: str | None = Field(default=None, max_length=2000)
    scheduling_require_email: bool | None = None
    is_active: bool | None = None


class AgentOut(ORMModel):
    id: uuid.UUID
    client_id: uuid.UUID
    is_template: bool = False
    template_label: str = ""
    cloned_from_agent_id: uuid.UUID | None = None
    provider: str
    name: str
    description: str
    instructions: str
    personality: str
    brief_summary: str
    brief_products: str
    brief_audience: str
    brief_policies: str
    brief_goal: str
    brief_dos: str
    brief_donts: str
    model: str
    timezone: str
    manual_context: str
    temperature: float
    max_tokens: int
    memory_limit: int
    session_gap_hours: int = 6
    history_max_age_days: int = 7
    reply_delay_seconds: int = 8
    image_enabled: bool
    image_model: str
    audio_enabled: bool
    audio_model: str
    widget_enabled: bool
    widget_public_id: str
    widget_greeting: str
    widget_color: str
    widget_position: str
    scheduling_enabled: bool = False
    scheduling_owner_email: str = ""
    scheduling_location: str = ""
    scheduling_duration_minutes: int = 60
    scheduling_hours: str = ""
    scheduling_require_email: bool = True
    is_active: bool
    created_at: datetime
    updated_at: datetime
    client: ClientOut


class ManualContextRequest(BaseModel):
    manual_context: str


class QAPairCreate(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1, max_length=8000)


class QAPairOut(ORMModel):
    id: uuid.UUID
    question: str
    answer: str


class ModelCatalogOut(BaseModel):
    id: str
    provider: str
    label: str
    family: str
    context_window: int
    max_output_tokens: int
    supports_tools: bool
    supports_vision: bool
    input_price_per_1k: float
    output_price_per_1k: float
    badge: str = ""
    note: str = ""


class DocumentOut(ORMModel):
    id: uuid.UUID
    filename: str
    status: str
    error_message: str | None
    created_at: datetime
    character_count: int = 0


class ConversationCreate(BaseModel):
    agent_id: uuid.UUID


class ConversationOut(ORMModel):
    id: uuid.UUID
    client_id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    mode: str
    channel: str
    external_chat_id: str | None = None
    contact_name: str | None = None
    created_at: datetime
    updated_at: datetime
    preview: str = ""


class SourceOut(BaseModel):
    id: str
    filename: str
    excerpt: str = ""


class MessageOut(ORMModel):
    id: uuid.UUID
    role: str
    content: str
    sources: list[dict] = []
    tool_calls: list[dict] | None = None
    sender_type: str
    sender_name: str | None
    external_message_id: str | None = None
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class ConversationInboxOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    client_id: uuid.UUID
    title: str
    contact_name: str | None = None
    channel: str
    mode: str
    preview: str = ""
    unread: bool = False
    unread_count: int = 0
    updated_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=50000)


class ConversationModeUpdate(BaseModel):
    mode: str = Field(pattern=r"^(ai|human)$")


class PortalLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PortalPublicOut(BaseModel):
    client_name: str
    portal_title: str
    portal_slug: str
    agency_name: str
    agency_brand_color: str
    agency_logo_url: str | None


class PortalSessionOut(BaseModel):
    client_id: uuid.UUID
    client_name: str
    portal_slug: str
    agency_name: str


class PortalUsageOut(BaseModel):
    """What the client sees about their own consumption. No cost, no margin."""
    used_tokens: int
    limit_tokens: int
    percentage_used: float
    is_blocked: bool
    unlimited: bool
    cycle_start: datetime
    cycle_end: datetime
    conversations: int
    human_conversations: int
    ai_messages: int
    human_messages: int


class DashboardOut(BaseModel):
    clients: int
    active_clients: int
    agents: int
    active_agents: int
    conversations: int
    channels: int
    connected_channels: int
    recent_agents: list[AgentSummary]


class DailyPoint(BaseModel):
    date: str
    count: int


class TopAgent(BaseModel):
    id: uuid.UUID
    name: str
    conversations: int


class ModelUsage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int


class DashboardMetrics(BaseModel):
    messages: int
    human_conversations: int
    by_channel: dict[str, int]
    daily_conversations: list[DailyPoint]
    top_agents: list[TopAgent]
    tokens_in: int
    tokens_out: int
    usage_by_model: list[ModelUsage]


class WhatsAppChannelUpdate(BaseModel):
    agent_id: uuid.UUID


class WhatsAppChannelOut(ORMModel):
    id: uuid.UUID
    client_id: uuid.UUID
    agent_id: uuid.UUID
    status: str
    phone_number: str | None
    display_name: str | None
    qr_code: str | None = None
    last_error: str | None
    is_enabled: bool
    has_session: bool = False
    last_connected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WhatsAppInternalAuth(BaseModel):
    auth_state: dict


class WhatsAppInternalStatus(BaseModel):
    status: str = Field(pattern=r"^(disconnected|connecting|qr|connected|reconnecting|error)$")
    phone_number: str | None = None
    display_name: str | None = None
    qr_code: str | None = None
    error: str | None = None


class WidgetConfigOut(BaseModel):
    title: str
    greeting: str
    color: str
    position: str
    agency_name: str
    agency_logo_url: str | None = None


class WidgetMessageIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=8000)


class WidgetMessageOut(BaseModel):
    role: str
    content: str


class WidgetReply(BaseModel):
    mode: str
    reply: str | None = None
    messages: list[WidgetMessageOut] = []


class WhatsAppInbound(BaseModel):
    external_message_id: str = Field(min_length=1, max_length=255)
    remote_jid: str = Field(min_length=1, max_length=255)
    sender_name: str | None = Field(default=None, max_length=180)
    text: str = Field(default="", max_length=50000)
    # Optional media (base64) for voice notes / images, processed by the agent's
    # audio/image capabilities before reaching the model.
    media_kind: str | None = Field(default=None, pattern=r"^(image|audio)$")
    media_base64: str | None = None
    media_mime: str | None = Field(default=None, max_length=100)


class WhatsAppInboundResult(BaseModel):
    accepted: bool
    reply: str | None = None
    conversation_id: uuid.UUID | None = None
    mode: str | None = None
    outbound_message_id: uuid.UUID | None = None


class WhatsAppOutboundConfirm(BaseModel):
    message_id: uuid.UUID
    external_message_id: str = Field(min_length=1, max_length=255)
