export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  agency: Agency;
};

export type Agency = { id: string; name: string; slug: string; brand_color: string; logo_url: string | null };

export type AgentSummary = { id: string; name: string; description: string; is_active: boolean };

export type Client = {
  id: string;
  name: string;
  industry: string;
  description: string;
  general_context: string;
  is_active: boolean;
  portal_slug: string;
  portal_enabled: boolean;
  portal_title: string;
  portal_email: string | null;
  portal_password_configured: boolean;
  portal_domain: string | null;
  portal_domain_verified: boolean;
  // Billing. `created_by_user_id` is the seller who registered the client and
  // is the portfolio isolation key; it is set server-side, never sent.
  created_by_user_id: string | null;
  billing_mode: BillingMode;
  monthly_fee_mxn: string;
  monthly_token_limit: number;
  billing_anchor_day: number;
  // Derived per request from usage records over the current cycle.
  used_tokens_current_cycle: number;
  percentage_tokens_used: number;
  is_blocked: boolean;
  cycle_start: string | null;
  cycle_end: string | null;
  agents: AgentSummary[];
  created_at: string;
  updated_at: string;
};

export type ClientDomain = {
  domain: string | null;
  verified: boolean;
  txt_host: string | null;
  txt_value: string | null;
};

export type Agent = {
  id: string;
  client_id: string;
  provider: string;
  name: string;
  description: string;
  instructions: string;
  personality: string;
  brief_summary: string;
  brief_products: string;
  brief_audience: string;
  brief_policies: string;
  brief_goal: string;
  brief_dos: string;
  brief_donts: string;
  model: string;
  timezone: string;
  manual_context: string;
  temperature: number;
  max_tokens: number;
  memory_limit: number;
  session_gap_hours: number;
  history_max_age_days: number;
  reply_delay_seconds: number;
  image_enabled: boolean;
  image_model: string;
  audio_enabled: boolean;
  audio_model: string;
  widget_enabled: boolean;
  widget_public_id: string;
  widget_greeting: string;
  widget_color: string;
  widget_position: string;
  is_active: boolean;
  // Shared as a reusable template for the whole agency.
  is_template: boolean;
  template_label: string;
  cloned_from_agent_id: string | null;
  client: Client;
  created_at: string;
  updated_at: string;
};

export type Provider = {
  provider: string;
  label: string;
  configured: boolean;
  api_key_masked: string;
  // Effective endpoint: the stored override, or the provider default.
  base_url: string | null;
};

export type BillingMode = "plan" | "pay_as_you_go" | "byok";

export type AgencyUser = {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
};

export type SellerMetrics = {
  worker_id: string;
  worker_name: string;
  worker_email: string;
  clients_count: number;
  monthly_revenue_mxn: number;
  ai_cost_mxn: number;
  margin_mxn: number;
  tokens_consumed: number;
};

export type ClientFinanceMetrics = {
  client_id: string;
  client_name: string;
  seller_name: string;
  billing_mode: string;
  monthly_fee_mxn: number;
  ai_cost_mxn: number;
  margin_mxn: number;
  tokens_used: number;
  monthly_token_limit: number;
  usage_pct: number;
  is_blocked: boolean;
};

export type FinanceDashboard = {
  total_clients: number;
  total_monthly_revenue_mxn: number;
  // Real, from the immutable cost snapshot on each usage record.
  total_ai_cost_mxn: number;
  total_margin_mxn: number;
  margin_pct: number;
  total_tokens_consumed: number;
  unpriced_usage_records: number;
  workers_metrics: SellerMetrics[];
  clients_metrics: ClientFinanceMetrics[];
};

/** What the client sees about their own consumption. No cost, no margin. */
export type PortalUsage = {
  used_tokens: number;
  limit_tokens: number;
  percentage_used: number;
  is_blocked: boolean;
  unlimited: boolean;
  cycle_start: string;
  cycle_end: string;
  conversations: number;
  human_conversations: number;
  ai_messages: number;
  human_messages: number;
};

export type ProviderTest = { ok: boolean; message: string; models: string[] };

export type KnowledgeDocument = {
  id: string;
  filename: string;
  status: "processed" | "error" | "pending";
  error_message: string | null;
  character_count: number;
  created_at: string;
};

export type QAPair = { id: string; question: string; answer: string };

export type ToolParam = { name: string; type: "string" | "number" | "integer" | "boolean"; description: string; required: boolean };
export type McpCachedTool = { name: string; description: string; input_schema?: Record<string, unknown> };
export type AgentTool = {
  id: string;
  agent_id: string;
  type: "http" | "mcp";
  name: string;
  description: string;
  enabled: boolean;
  url: string;
  http_method: string;
  prompt_instructions: string;
  body_params: ToolParam[];
  query_params: ToolParam[];
  timeout_seconds: number;
  transport: "sse" | "streamable_http";
  cached_tools: McpCachedTool[];
  tools_cached_at: string | null;
  has_headers: boolean;
  created_at: string;
  updated_at: string;
};
export type ToolCallMeta = { name: string; arguments: Record<string, unknown>; result_preview: string; is_error: boolean };

export type Source = { id: string; filename: string; excerpt: string };
export type Message = { id: string; role: "user" | "assistant"; content: string; sources: Source[]; tool_calls?: ToolCallMeta[] | null; sender_type: "visitor" | "ai" | "human"; sender_name: string | null; created_at: string };

export type ConversationInbox = {
  id: string;
  agent_id: string;
  agent_name: string;
  client_id: string;
  title: string;
  contact_name: string | null;
  channel: string;
  mode: "ai" | "human";
  preview: string;
  unread: boolean;
  unread_count: number;
  updated_at: string;
};
export type Conversation = {
  id: string;
  client_id: string;
  agent_id: string;
  title: string;
  mode: "ai" | "human";
  channel: string;
  external_chat_id: string | null;
  contact_name: string | null;
  created_at: string;
  updated_at: string;
  preview?: string;
  messages?: Message[];
};

export type WhatsAppChannel = {
  id: string;
  client_id: string;
  agent_id: string;
  status: "disconnected" | "connecting" | "qr" | "connected" | "reconnecting" | "error";
  phone_number: string | null;
  display_name: string | null;
  qr_code: string | null;
  last_error: string | null;
  is_enabled: boolean;
  has_session: boolean;
  last_connected_at: string | null;
  created_at: string;
  updated_at: string;
};

export type WhatsAppCloudChannel = {
  id: string;
  client_id: string;
  agent_id: string;
  status: "disconnected" | "connected" | "error";
  phone_number: string | null;
  display_name: string | null;
  phone_number_id: string;
  waba_id: string | null;
  has_access_token: boolean;
  has_app_secret: boolean;
  webhook_url: string;
  webhook_verify_token: string;
  last_error: string | null;
  is_enabled: boolean;
  last_connected_at: string | null;
  created_at: string;
  updated_at: string;
};

/** Facebook Messenger and Instagram Direct share one channel shape. */
export type MetaPlatform = "messenger" | "instagram";

export type MetaChannel = {
  id: string;
  client_id: string;
  agent_id: string;
  platform: MetaPlatform;
  status: "disconnected" | "connected" | "error";
  // Page id for Messenger, Instagram user id for Instagram.
  account_id: string;
  account_name: string | null;
  has_access_token: boolean;
  has_app_secret: boolean;
  webhook_url: string;
  webhook_verify_token: string;
  last_error: string | null;
  is_enabled: boolean;
  last_connected_at: string | null;
  created_at: string;
  updated_at: string;
};

/** One model from the backend catalog (/api/catalog/models). */
export type CatalogModel = {
  id: string;
  provider: string;
  label: string;
  family: string;
  context_window: number;
  max_output_tokens: number;
  supports_tools: boolean;
  supports_vision: boolean;
  input_price_per_1k: number;
  output_price_per_1k: number;
  badge: string;
  note: string;
};

export type AgentTemplate = {
  id: string;
  name: string;
  template_label: string;
  description: string;
  industry: string;
  source_client_name: string;
  provider: string;
  model: string;
  qa_count: number;
  document_count: number;
  tool_count: number;
  updated_at: string;
};

export type AgencySettings = {
  emails_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  has_smtp_password: boolean;
  smtp_use_tls: boolean;
  smtp_from_email: string;
  smtp_from_name: string;
  owner_alert_email: string;
  notify_seller_on_quota: boolean;
  notify_client_on_quota: boolean;
  pool_degrade_percent: number;
  pool_block_percent: number;
  pool_fallback_model: string;
  pool_alert_percent: number;
  updated_at: string;
};

export type ModelPrice = {
  id: string;
  provider: string;
  model: string;
  input_price_per_1k_usd: number;
  output_price_per_1k_usd: number;
  effective_from: string;
  origin: string;
  note: string;
  created_at: string;
};

export type PoolWindow = { name: string; percent: number; status: string; resets_at: string };

export type PoolStatus = {
  provider: string;
  label: string;
  configured: boolean;
  percent: number;
  status: string;
  degraded: boolean;
  blocked: boolean;
  windows: PoolWindow[];
  captured_at: string | null;
  tokens_at_capture: number;
  // Measured capacity: our tokens per percentage point. Null until measured.
  tokens_per_percent: number | null;
};

export type ModelSyncReport = {
  checked_providers: string[];
  unreachable: { provider: string; base_url: string }[];
  retired: { provider: string; model: string }[];
  new_models: { provider: string; model: string }[];
  agents_at_risk: { client_name: string; agent_name: string; model: string }[];
  has_changes: boolean;
};

export type PortalPublic = {
  client_name: string;
  portal_title: string;
  portal_slug: string;
  agency_name: string;
  agency_brand_color: string;
  agency_logo_url: string | null;
};
