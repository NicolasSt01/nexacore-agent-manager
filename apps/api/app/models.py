import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def new_public_id() -> str:
    return uuid.uuid4().hex


def new_domain_token() -> str:
    return uuid.uuid4().hex


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(180))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    brand_color: Mapped[str] = mapped_column(String(20), default="#075985")
    logo_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    logo_mime: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    users: Mapped[list["User"]] = relationship(back_populates="agency", cascade="all, delete-orphan")

    @property
    def logo_url(self) -> str | None:
        return f"/api/agency/logo?v={int(self.created_at.timestamp())}" if self.logo_data else None


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    agency: Mapped[Agency] = relationship(back_populates="users")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    industry: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    general_context: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    portal_slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    portal_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    portal_title: Mapped[str] = mapped_column(String(180), default="")
    portal_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    portal_password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Optional custom domain for this client's portal. Verified via a DNS TXT
    # challenge; only verified domains are routed and get an on-demand cert.
    portal_domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    portal_domain_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    portal_domain_token: Mapped[str] = mapped_column(String(64), default="", server_default="")
    
    # Financial & Token billing configuration
    billing_mode: Mapped[str] = mapped_column(String(30), default="plan", server_default="plan")  # "plan", "pay_as_you_go", "byok"
    # Money is stored as Numeric, never Float: binary floats cannot represent
    # decimal amounts exactly and the error accumulates across aggregations.
    monthly_fee_mxn: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("200.00"), server_default="200.00")
    monthly_token_limit: Mapped[int] = mapped_column(Integer, default=500000, server_default="500000")  # 0 for unlimited
    # Cycle cut day, taken from the signup date: a client registered on the 12th
    # cuts on the 12th of every month. See services/billing.cycle_window.
    billing_anchor_day: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # Stamps for the once-per-cycle quota notifications, so a hundred messages
    # arriving after the limit do not send a hundred emails.
    quota_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quota_blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    encrypted_client_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    created_by_user: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    agents: Mapped[list["Agent"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    whatsapp_channel: Mapped["WhatsAppChannel | None"] = relationship(
        back_populates="client", cascade="all, delete-orphan", uselist=False
    )
    whatsapp_cloud_channel: Mapped["WhatsAppCloudChannel | None"] = relationship(
        back_populates="client", cascade="all, delete-orphan", uselist=False
    )
    meta_channels: Mapped[list["MetaMessagingChannel"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )

    @property
    def portal_password_configured(self) -> bool:
        return bool(self.portal_password_hash)


class AgencySettings(Base):
    """Global, superadmin-managed settings for one agency.

    Kept apart from Agency (branding, shown to everyone) because these are
    operational secrets: only a superadmin reads or writes them.
    """

    __tablename__ = "agency_settings"
    __table_args__ = (UniqueConstraint("agency_id", name="uq_agency_settings_agency"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)

    # --- Outbound email ----------------------------------------------------
    emails_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    smtp_host: Mapped[str] = mapped_column(String(255), default="", server_default="")
    smtp_port: Mapped[int] = mapped_column(Integer, default=587, server_default="587")
    smtp_user: Mapped[str] = mapped_column(String(255), default="", server_default="")
    encrypted_smtp_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    smtp_from_email: Mapped[str] = mapped_column(String(320), default="", server_default="")
    smtp_from_name: Mapped[str] = mapped_column(String(180), default="", server_default="")
    # Where the daily model-catalog report and other owner alerts are sent.
    owner_alert_email: Mapped[str] = mapped_column(String(320), default="", server_default="")

    # --- Quota notifications ----------------------------------------------
    notify_seller_on_quota: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notify_client_on_quota: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # --- Shared subscription pool (circuit breaker) ------------------------
    # Past this share of the pool, agents fall back to a model that does not
    # consume it, instead of every client failing at once.
    pool_degrade_percent: Mapped[int] = mapped_column(Integer, default=80, server_default="80")
    # Past this, stop replying and hand over to a human.
    pool_block_percent: Mapped[int] = mapped_column(Integer, default=95, server_default="95")
    # Model used while degraded, e.g. "ox-alpha-free" (unlimited on OpenCode GO).
    # Empty means no degradation step: go straight from OK to blocked.
    pool_fallback_model: Mapped[str] = mapped_column(String(180), default="", server_default="")
    # Owner alert once any window crosses this.
    pool_alert_percent: Mapped[int] = mapped_column(Integer, default=70, server_default="70")
    pool_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class ProviderCredential(Base):
    """One AI provider API key per agency (bring your own key). provider is
    "openai", "anthropic", "openrouter", "deepseek", etc. base_url overrides default."""

    __tablename__ = "provider_credentials"
    __table_args__ = (UniqueConstraint("agency_id", "provider", name="uq_provider_credentials_agency_provider"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    encrypted_api_key: Mapped[str] = mapped_column(Text)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    # Structured business brief. Optional guided fields that compose into the
    # system prompt alongside the free-form instructions.
    brief_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    brief_products: Mapped[str] = mapped_column(Text, default="", server_default="")
    brief_audience: Mapped[str] = mapped_column(Text, default="", server_default="")
    brief_policies: Mapped[str] = mapped_column(Text, default="", server_default="")
    brief_goal: Mapped[str] = mapped_column(Text, default="", server_default="")
    brief_dos: Mapped[str] = mapped_column(Text, default="", server_default="")
    brief_donts: Mapped[str] = mapped_column(Text, default="", server_default="")
    # AI provider ("openai" or "anthropic"); the agency's key for that provider is used.
    provider: Mapped[str] = mapped_column(String(30), default="openai", server_default="openai")
    model: Mapped[str] = mapped_column(String(180), default="")
    # IANA timezone (e.g. "America/Bogota"); injected into the system prompt so
    # the agent knows the local date/time. "UTC" when unset.
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    manual_context: Mapped[str] = mapped_column(Text, default="")
    # Generation settings. Sampling params are applied best-effort by the AI
    # service (models that reject them fall back to their defaults).
    temperature: Mapped[float] = mapped_column(Float, default=0.7, server_default="0.7")
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, server_default="2048")
    # --- Conversation memory (see services/history.py) ---------------------
    # How many past messages are kept as conversation memory. 20 covers a full
    # enquiry; more mostly drags stale context into the prompt.
    memory_limit: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    # A gap wider than this ends the session: a morning enquiry and its
    # afternoon follow-up belong together, the next day does not. 0 disables.
    session_gap_hours: Mapped[int] = mapped_column(Integer, default=6, server_default="6")
    # Raw messages older than this never enter the prompt, whatever the count
    # allows. Continuity beyond it is the job of the contact summary. 0 disables.
    history_max_age_days: Mapped[int] = mapped_column(Integer, default=7, server_default="7")
    # How long to wait for the contact to finish before replying. People write
    # in fragments ("sí" … "para el lunes" … "en la mañana"); answering the
    # first one produces three replies to half a thought. Each new message
    # pushes the wait forward, so the agent answers the complete idea once.
    # 0 replies immediately.
    reply_delay_seconds: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    # Multimodal capabilities. When enabled, inbound images are described by a
    # vision model and inbound audio is transcribed before reaching the agent.
    image_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    image_model: Mapped[str] = mapped_column(String(180), default="", server_default="")
    audio_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    audio_model: Mapped[str] = mapped_column(String(180), default="whisper-1", server_default="whisper-1")
    # Embeddable web chat widget.
    widget_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    widget_public_id: Mapped[str] = mapped_column(String(64), default=new_public_id, unique=True, index=True)
    widget_greeting: Mapped[str] = mapped_column(Text, default="", server_default="")
    widget_color: Mapped[str] = mapped_column(String(20), default="", server_default="")
    widget_position: Mapped[str] = mapped_column(String(10), default="right", server_default="right")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Shared as a reusable template: a polished agent (e.g. "Dental clinic
    # receptionist") that any seller in the agency may clone onto a new client
    # of the same kind. Sharing exposes only the configuration for cloning —
    # never the source client's conversations or documents' ownership.
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    template_label: Mapped[str] = mapped_column(String(180), default="", server_default="")
    # The template this agent was cloned from, kept so we can tell which
    # templates are actually being reused.
    cloned_from_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    client: Mapped[Client] = relationship(back_populates="agents")
    documents: Mapped[list["KnowledgeDocument"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    qa_pairs: Mapped[list["AgentQA"]] = relationship(back_populates="agent", cascade="all, delete-orphan", order_by="AgentQA.position")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    whatsapp_channels: Mapped[list["WhatsAppChannel"]] = relationship(back_populates="agent")
    whatsapp_cloud_channels: Mapped[list["WhatsAppCloudChannel"]] = relationship(back_populates="agent")
    meta_channels: Mapped[list["MetaMessagingChannel"]] = relationship(back_populates="agent")
    tools: Mapped[list["AgentTool"]] = relationship(back_populates="agent", cascade="all, delete-orphan", order_by="AgentTool.created_at")


class AgentTool(Base):
    """A custom tool the agent can call: a user-defined HTTP endpoint
    ("http") or an external MCP server ("mcp")."""

    __tablename__ = "agent_tools"
    __table_args__ = (UniqueConstraint("agent_id", "name", name="uq_agent_tools_agent_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # HTTP endpoint (may contain {param} path placeholders) or MCP server URL.
    url: Mapped[str] = mapped_column(Text, default="")
    # HTTP tools only.
    http_method: Mapped[str] = mapped_column(String(10), default="GET")
    prompt_instructions: Mapped[str] = mapped_column(Text, default="")
    body_params: Mapped[list] = mapped_column(JSON, default=list)
    query_params: Mapped[list] = mapped_column(JSON, default=list)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    # MCP servers only. cached_tools holds the last list_tools result so chat
    # requests never block on discovery; refreshed on save/test-connection.
    transport: Mapped[str] = mapped_column(String(20), default="streamable_http")
    cached_tools: Mapped[list] = mapped_column(JSON, default=list)
    tools_cached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The full auth headers dict, encrypted at rest; never returned by the API.
    encrypted_headers: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    agent: Mapped[Agent] = relationship(back_populates="tools")


class WhatsAppChannel(Base):
    __tablename__ = "whatsapp_channels"
    __table_args__ = (UniqueConstraint("client_id", name="uq_whatsapp_channels_client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="disconnected")
    phone_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    encrypted_auth_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_qr: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    client: Mapped[Client] = relationship(back_populates="whatsapp_channel")
    agent: Mapped[Agent] = relationship(back_populates="whatsapp_channels")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="whatsapp_channel")


class WhatsAppCloudChannel(Base):
    """Official WhatsApp Business Cloud API channel (Meta Graph API). Coexists
    with the Baileys channel: a client can have one of each, on different
    numbers. Credentials are provided manually (bring your own Meta app)."""

    __tablename__ = "whatsapp_cloud_channels"
    __table_args__ = (UniqueConstraint("client_id", name="uq_whatsapp_cloud_channels_client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="disconnected")
    phone_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone_number_id: Mapped[str] = mapped_column(String(80), default="", server_default="")
    waba_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_app_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Token the owner pastes into their Meta app's webhook config; it must be
    # re-displayable, so it is stored in plain text like portal_domain_token.
    webhook_verify_token: Mapped[str] = mapped_column(String(64), default=new_public_id, server_default="")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    client: Mapped[Client] = relationship(back_populates="whatsapp_cloud_channel")
    agent: Mapped[Agent] = relationship(back_populates="whatsapp_cloud_channels")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="whatsapp_cloud_channel")


class MetaMessagingChannel(Base):
    """Facebook Messenger / Instagram Direct channel (Meta Messenger Platform).

    Both platforms speak the same webhook shape and the same Send API, differing
    only in the object type and the id the messages are posted to, so one table
    with a `platform` discriminator avoids duplicating the whole flow. A client
    can have one channel per platform. Credentials are provided manually (bring
    your own Meta app), like the WhatsApp Cloud channel.
    """

    __tablename__ = "meta_messaging_channels"
    __table_args__ = (UniqueConstraint("client_id", "platform", name="uq_meta_channels_client_platform"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), index=True)
    # "messenger" (a Facebook Page) or "instagram" (an IG professional account).
    platform: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="disconnected")
    # Page id for Messenger, Instagram user id for Instagram: the id inbound
    # messages are addressed to and outbound ones are posted to.
    account_id: Mapped[str] = mapped_column(String(80), default="", server_default="")
    account_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_app_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Pasted into the Meta app's webhook config, so it must stay re-displayable.
    webhook_verify_token: Mapped[str] = mapped_column(String(64), default=new_public_id, server_default="")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    client: Mapped[Client] = relationship(back_populates="meta_channels")
    agent: Mapped[Agent] = relationship(back_populates="meta_channels")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="meta_channel")


class AgentQA(Base):
    __tablename__ = "agent_qa"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    agent: Mapped[Agent] = relationship(back_populates="qa_pairs")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_data: Mapped[bytes] = mapped_column(LargeBinary)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="processed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    agent: Mapped[Agent] = relationship(back_populates="documents")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    # Embedding vector stored as a JSON array of floats (portable across any
    # Postgres; similarity is computed in Python). Swap to pgvector at scale.
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")


class UsageRecord(Base):
    __tablename__ = "usage_records"
    # Every quota check and every finance query aggregates a client's tokens
    # over a billing window; this index is what keeps that a cheap lookup.
    __table_args__ = (Index("ix_usage_records_client_created", "client_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    # Denormalized on purpose: agent_id is SET NULL on delete, so attribution
    # would be lost with the agent. Billing history must outlive the agent.
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(180))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    # Entry point that produced the usage: "whatsapp", "widget", "portal" or
    # "playground". Internal playground testing must not consume client quota.
    source: Mapped[str] = mapped_column(String(20), default="", server_default="")
    # --- Immutable cost snapshot -------------------------------------------
    # Frozen at write time. Recomputing cost from today's prices would rewrite
    # the margin of every past record the moment a provider changes a price.
    input_price_per_1k_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0"), server_default="0")
    output_price_per_1k_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0"), server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=Decimal("0"), server_default="0")
    usd_to_mxn: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"), server_default="0")
    cost_mxn: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("0"), server_default="0")
    # Where the price came from: "table", "catalog" or "unknown". Rows priced
    # "unknown" are surfaced in finance so they get fixed instead of silently
    # counting as zero cost.
    price_source: Mapped[str] = mapped_column(String(20), default="unknown", server_default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class SubscriptionUsage(Base):
    """A reading of a subscription provider's shared usage pool.

    Subscription gateways (OpenCode Zen / GO) do not bill per token: they meter
    one pool shared by every client on the key, with several windows at once
    (a rolling one, weekly, monthly). If the pool runs out, **every** client on
    that key stops at the same time — so the pool has to be watched, not the
    per-client quota alone.

    Snapshots are kept as history so we can learn the real capacity: how many
    of our own tokens move the percentage how much.
    """

    __tablename__ = "subscription_usage"
    __table_args__ = (Index("ix_subscription_usage_lookup", "agency_id", "provider", "captured_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    # Highest percentage across all windows: the one that will actually stop us.
    percent: Mapped[float] = mapped_column(Float, default=0.0)
    # Per-window detail as returned by the provider, kept verbatim.
    windows: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="ok", server_default="ok")
    # Our own billable tokens at capture time, to correlate pool % with usage.
    tokens_at_capture: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class ModelPrice(Base):
    """Versioned provider price for one model, in USD per 1,000 tokens.

    Prices change over time and a change must never rewrite history: what was
    earned yesterday stays as it was earned. So a price update is an INSERT of
    a new row with a later `effective_from`, never an UPDATE, and each usage
    record snapshots the price it actually used.
    """

    __tablename__ = "model_prices"
    __table_args__ = (
        UniqueConstraint("provider", "model", "effective_from", name="uq_model_prices_provider_model_from"),
        Index("ix_model_prices_lookup", "provider", "model", "effective_from"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(180))
    input_price_per_1k_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0"))
    output_price_per_1k_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0"))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    # "catalog" when seeded from the static catalog, "manual" when a superadmin
    # entered it, "sync" when the daily refresh picked up a provider change.
    origin: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class FxRate(Base):
    """Daily USD->MXN reference rate. Providers bill in USD, NexaCore charges in
    MXN, so the rate applied is snapshotted per usage record too."""

    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("base", "quote", "rate_date", name="uq_fx_rates_pair_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    base: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    quote: Mapped[str] = mapped_column(String(3), default="MXN", server_default="MXN")
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    rate_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(30), default="banxico_fix", server_default="banxico_fix")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("whatsapp_channel_id", "external_chat_id", name="uq_conversations_whatsapp_chat"),
        UniqueConstraint(
            "whatsapp_cloud_channel_id", "external_chat_id", name="uq_conversations_whatsapp_cloud_chat"
        ),
        UniqueConstraint("meta_channel_id", "external_chat_id", name="uq_conversations_meta_chat"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240), default="New conversation")
    mode: Mapped[str] = mapped_column(String(30), default="ai")
    channel: Mapped[str] = mapped_column(String(40), default="playground")
    whatsapp_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("whatsapp_channels.id", ondelete="CASCADE"), nullable=True, index=True
    )
    whatsapp_cloud_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("whatsapp_cloud_channels.id", ondelete="CASCADE"), nullable=True, index=True
    )
    meta_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meta_messaging_channels.id", ondelete="CASCADE"), nullable=True, index=True
    )
    external_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    operator_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # --- Contact summary (see services/summary.py) --------------------------
    # A compact card of who this contact is and what was left pending, rebuilt
    # when a session closes. It carries continuity across days at a fixed cost,
    # instead of dragging the whole transcript into every prompt.
    contact_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    # created_at of the newest message the summary covers: tells us what is new
    # to fold in, and how stale the card is.
    contact_summary_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the pending batch of inbound messages should be answered. Set on
    # every inbound message and pushed forward by the next one; the worker in
    # services/replies.py picks it up. NULL means nothing is pending.
    reply_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    agent: Mapped[Agent] = relationship(back_populates="conversations")
    whatsapp_channel: Mapped[WhatsAppChannel | None] = relationship(back_populates="conversations")
    whatsapp_cloud_channel: Mapped[WhatsAppCloudChannel | None] = relationship(back_populates="conversations")
    meta_channel: Mapped["MetaMessagingChannel | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "external_message_id", name="uq_messages_conversation_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    # Tool usage behind an assistant reply: [{name, arguments, result_preview, is_error}].
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sender_type: Mapped[str] = mapped_column(String(30), default="visitor")
    sender_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
