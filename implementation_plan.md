# Implementation Plan — NexaCore Agent Manager: Seller Scoping, Billing & Token Quotas

> Written in English per the repo language convention (`CLAUDE.md`). Only end-user UI copy is
> localized, through the typed i18n system in `apps/web/lib/i18n`.

This plan covers the monetization model for **NexaCore Agent Manager**, the low-cost AI providers
(OpenCode, OpenRouter, DeepSeek, Qwen), immutable cost accounting, per-client token quotas with hard
enforcement, and the seller-level portfolio isolation for Edgar and Enedina.

---

## 0. Locked decisions

These were decided up front and constrain everything below. Do not re-open them mid-implementation.

| # | Decision | Consequence |
|---|---|---|
| 1 | **One agency (NexaCore) with seller users.** Edgar and Enedina are `users` of the NexaCore agency, each registering their own clients. | `agency_id` stays the tenant boundary, but a **second isolation axis** (`owner_user_id` on `Client`) is layered on top and must be enforced on *every* resource that hangs off a client. |
| 2 | **Prices change over time and must never rewrite history.** If a model's price rises tomorrow, yesterday's margin stays as it was earned. | Cost is **snapshotted into each usage record** at write time. Prices live in a versioned table with `effective_from`. |
| 3 | **FX from Banco de México (daily)**, until a specific bank is chosen. | Daily FIX rate fetched and cached in a `fx_rates` table; the rate used is **also snapshotted** per usage record. Swapping the source later is a single service change. |
| 4 | **Billing cycle is anchored to the client's signup day.** A client registered on the 12th cuts on the 12th of each month. | No global monthly reset job. The cycle window is *derived* from `billing_anchor_day`, and consumption is a `SUM` over `usage_records` inside that window. |
| 5 | **Hard enforcement.** On quota exhaustion, automatic AI replies stop, the client is notified by email, and the conversation falls back to manual handling. | A single quota gate runs *before* every LLM call. Conversations flip to `mode="human"`. |
| 6 | **Finance MVP is projection only.** Accounting issues invoices and records payments outside this product. | No `invoices` / `payments` tables. The finance module reports *projected* revenue, real AI cost, and margin. |
| 7 | **Providers to support:** OpenCode (Zen / GO subscription), OpenRouter, DeepSeek, Qwen — plus the existing OpenAI and Anthropic. | Requires a third API dialect (`/chat/completions`) in `services/ai.py` and per-credential `base_url`. |

---

## 1. Commercial architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 💰 BILLING MODES PER CLIENT (Client.billing_mode)                                       │
│                                                                                        │
│ 📌 "plan" — Token package (default, MXN)                                                │
│    • The client pays a monthly subscription (e.g. $200 MXN / 500,000 tokens).           │
│    • NexaCore covers the underlying cost through low-cost providers and keeps the       │
│      spread as margin.                                                                 │
│    • Hard limit: on exhaustion the AI stops replying and the client is emailed.         │
│                                                                                        │
│ 📌 "pay_as_you_go" — Metered                                                             │
│    • All tokens consumed in the cycle are recorded; billed at real cost + markup.       │
│    • No hard cap by default; an optional `monthly_token_limit` acts as a safety stop.   │
│                                                                                        │
│ 📌 "byok" — Bring Your Own Key                                                           │
│    • The client supplies their own provider API key; NexaCore charges a flat platform   │
│      fee. Usage is still recorded (for reporting) but never quota-blocked.              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Role hierarchy

```
👑 SUPERADMIN (Nicolás — owner)          role = "superadmin"
   • Sees every client of the agency, regardless of which seller registered it.
   • Consolidated finance view: projected revenue (MXN), real AI cost, net margin,
     breakdown per seller and per client.
   • Manages provider credentials and the model price table.

👔 SELLER (Edgar, Enedina)               role = "seller"
   • Registers clients; each new client gets owner_user_id = the seller's id.
   • Sees ONLY their own portfolio — clients, agents, conversations, usage, channels.
   • Assigns the billing mode and plan at client creation; cannot edit model prices
     or provider credentials.

🏥 END CLIENT (portal, separate auth — not a `users` row)
   • White-label portal at /portal/[slug]: KPIs, token progress bar, WhatsApp QR,
     and (BYOK only) their own API key field.
   • Never sees or edits models, prompts, or provider settings.
```

> `role = "admin"` (the current default in `models.py:53`) is kept as a synonym of `superadmin`
> during migration so nothing breaks; the seed user is upgraded to `superadmin`.

---

## 2. Backend changes

### 2.1 Authorization — this does not exist yet

`User.role` is declared at `apps/api/app/models.py:53` and is **referenced nowhere else in the
backend**. Every one of the 32 `agency_id ==` filters across `app/routers/` grants full access to any
authenticated user. This is the foundation; build it first.

**New in `apps/api/app/deps.py`:**

```python
ROLE_SUPERADMIN = "superadmin"
ROLE_SELLER = "seller"

def require_superadmin(user: User = Depends(get_current_user)) -> User: ...
def is_superadmin(user: User) -> bool: ...   # treats legacy "admin" as superadmin
```

**New in `apps/api/app/services/scoping.py` — the single source of truth for visibility:**

```python
def visible_client_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Client ids the user may see. None means 'all clients in the agency'
    (superadmin) so callers can skip the extra filter."""

def scope_clients(stmt, user):  ...   # applies agency_id + owner_user_id to a select()
def assert_client_visible(db, user, client_id) -> Client:  ...  # 404 (not 403) if not owned
```

Return **404, not 403**, when a seller requests another seller's client — a 403 confirms the
resource exists and leaks portfolio information.

**Routers that must adopt the scoping helper** (each currently filters by `agency_id` only):

| File | What leaks today without the change |
|---|---|
| `routers/clients.py` | Full client list across sellers |
| `routers/agents.py` | Agents belonging to another seller's clients |
| `routers/conversations.py` | Conversations and message history |
| `routers/dashboard.py` | Aggregate counts and token usage |
| `routers/whatsapp.py`, `routers/whatsapp_cloud.py` | Channels, QR pairing, session state |
| `routers/agent_tools.py` | Tool definitions attached to another seller's agents |
| `routers/portal.py` | Portal config for another seller's client |

`routers/providers.py` and the new price endpoints become **superadmin-only**.

> **Testing note:** this is an authorization surface, so it is covered by `pytest` (fast,
> deterministic, one test per endpoint), not by Playwright. See §6.

### 2.2 Data model (`apps/api/app/models.py`)

**`Client` — new columns:**

| Column | Type | Notes |
|---|---|---|
| `owner_user_id` | FK `users.id`, nullable, indexed | The seller who registered the client. Nullable so existing rows migrate; backfilled to the seed superadmin. `ON DELETE SET NULL`. |
| `billing_mode` | `String(20)`, default `"plan"` | `"plan"` \| `"pay_as_you_go"` \| `"byok"` |
| `monthly_fee_mxn` | `Numeric(10, 2)`, default `0` | What the client pays per cycle. **Never `Float`** — money is decimal. |
| `monthly_token_limit` | `Integer`, default `0` | `0` = unlimited. |
| `billing_anchor_day` | `Integer`, default from `created_at.day` | Cycle cut day (1–31, clamped for short months). |
| `quota_warned_at` | `DateTime`, nullable | Last 80%-threshold email, so it fires once per cycle. |
| `quota_blocked_at` | `DateTime`, nullable | When the hard block engaged in the current cycle. |
| `byok_provider` | `String(30)`, nullable | Provider for the client's own key. |
| `byok_base_url` | `String(255)`, nullable | Overrides the provider default. |
| `encrypted_byok_api_key` | `Text`, nullable | Encrypted with `security.encrypt_secret` — same path as `provider_credentials`. |

**`UsageRecord` — new columns.** Today it stores only `agency_id`, `agent_id`, `provider`, `model`,
`input_tokens`, `output_tokens`. Since `agent_id` is `ON DELETE SET NULL`, deleting an agent
currently **destroys the billing attribution**. Fix:

| Column | Type | Notes |
|---|---|---|
| `client_id` | FK `clients.id`, **not null**, indexed | Denormalized on purpose: usage must survive agent deletion. |
| `owner_user_id` | FK `users.id`, nullable, indexed | Seller at the time of consumption; makes per-seller finance a single indexed query. |
| `input_price_per_1k_usd` | `Numeric(12, 8)` | **Snapshot** of the price used. |
| `output_price_per_1k_usd` | `Numeric(12, 8)` | **Snapshot.** |
| `cost_usd` | `Numeric(14, 8)` | Computed at write time from the snapshot. |
| `usd_to_mxn` | `Numeric(10, 6)` | **Snapshot** of the FX rate applied. |
| `cost_mxn` | `Numeric(14, 6)` | `cost_usd * usd_to_mxn`, frozen. |
| `price_source` | `String(20)` | `"table"` \| `"catalog"` \| `"unknown"` — for auditing rows priced by fallback. |
| `source` | `String(20)` | `"whatsapp"` \| `"widget"` \| `"portal"` \| `"playground"` \| `"tool"` — needed to exclude internal playground traffic from client quotas. |

Index: `(client_id, created_at)` — every quota check and every finance query hits it.

**New `ModelPrice`** — versioned prices, so a change tomorrow does not alter yesterday's margin:

```
model_prices
  id, provider, model,
  input_price_per_1k_usd  Numeric(12, 8),
  output_price_per_1k_usd Numeric(12, 8),
  effective_from          DateTime (indexed),
  created_at, created_by_user_id
  UNIQUE (provider, model, effective_from)
```

Resolution: latest row with `effective_from <= now()` for `(provider, model)`. A price update is an
**insert**, never an update. Seeded from the existing static catalog in
`apps/api/app/services/model_catalog.py` (which already carries `input_price_per_1k` /
`output_price_per_1k` in USD).

**New `FxRate`** — daily Banxico FIX:

```
fx_rates
  id, base ("USD"), quote ("MXN"), rate Numeric(10, 6),
  rate_date Date, source String(30) ("banxico_fix"), fetched_at
  UNIQUE (base, quote, rate_date)
```

### 2.3 Pricing and FX services

**`apps/api/app/services/pricing.py`** (new)

```python
def resolve_price(db, provider: str, model: str, at: datetime) -> PriceSnapshot
```
Order: `model_prices` (→ `price_source="table"`) → static `model_catalog` (→ `"catalog"`) → zeros
with `"unknown"`. An unknown price **never blocks a reply** — it records zero cost and is surfaced in
the finance view as "unpriced usage" so it gets fixed. Silent zero-cost rows are how margin
reporting quietly goes wrong.

**`apps/api/app/services/fx.py`** (new)

```python
def usd_to_mxn(db, on: date) -> Decimal
```
Reads today's `fx_rates` row; on a miss, fetches the Banxico FIX series (SIE API, token in
`banxico_token` config) and caches it. On failure, falls back to the **most recent stored rate** and
logs it — an FX outage must not stop the product. A configurable `fx_fallback_usd_mxn` setting seeds
the very first run.

The rate is fetched at most once per day. Weekends and Mexican bank holidays have no FIX
publication, so the last published rate carries forward — this is the correct behavior, not a bug.

### 2.4 Billing cycle (`apps/api/app/services/billing.py`, new)

```python
def cycle_window(client: Client, at: datetime) -> tuple[datetime, datetime]
```
Derives `[start, end)` from `billing_anchor_day` in the agency timezone. A client anchored on the
31st cuts on the 30th in November and the 28th/29th in February — clamp, never skip a cycle.

```python
def tokens_used(db, client: Client, at: datetime) -> int          # SUM over the window
def quota_status(db, client: Client) -> QuotaStatus               # used, limit, pct, blocked, window
```

Consumption is **always derived** with a `SUM` over `usage_records` within the window — there is no
mutable `current_month_tokens_used` counter. A counter would need a reset job, would drift on
failure, and would be unauditable. The `(client_id, created_at)` index makes the aggregate cheap; if
it ever becomes a bottleneck, add a cache with a TTL — not a source of truth.

### 2.5 Quota enforcement — one gate, before the call

There are four entry points that reach the LLM today:

| Call site | Status |
|---|---|
| `routers/widget.py:136` | Records usage |
| `routers/conversations.py:211` | Records usage |
| `services/whatsapp_inbound.py:194` | Records usage |
| `services/tools/runner.py:50` | Already metered: `openai_tool_loop` / `anthropic_tool_loop` accumulate `input_tokens` / `output_tokens` across every round-trip and return them in the single `Completion` the call sites record. No change needed. |

**New `apps/api/app/services/quota.py`:**

```python
class QuotaExceeded(Exception): ...

def check_quota(db, client: Client, *, source: str) -> None
    """Raise QuotaExceeded when the client is out of tokens for the cycle.
    No-op for billing_mode == "byok", for monthly_token_limit == 0,
    and for source == "playground" (internal testing must not burn client quota)."""
```

Wire-up:
1. `check_quota` runs **before** every `chat_completion` call at all four sites.
2. `record_usage` gains `client_id` and `source` (**done**), and will do the price/FX snapshot
   internally so no call site can forget it.

**On `QuotaExceeded`, per channel:**

| Channel | Behavior |
|---|---|
| WhatsApp (`whatsapp_inbound.py`) | No AI reply is sent. Conversation flips to `mode="human"` and is flagged unread in the inbox so the seller sees it. **No automated "you ran out of credit" message is sent to the end consumer** — the patient messaging a dental clinic must never see NexaCore's billing state. |
| Web widget (`widget.py`) | Returns the agent's configured fallback message; the visitor sees a normal "we'll get back to you" reply, not an error. |
| Portal / internal playground | Explicit `402`-style error with a clear message for the operator. |

**Notifications** (once per cycle, guarded by `quota_warned_at` / `quota_blocked_at`):
- **80% reached** → warning email to the client's portal email, seller in copy.
- **100% reached** → block email to the client, and a notice to the owning seller and superadmin.

> ⚠️ **There is no email infrastructure in this repo today** — no SMTP client, no provider, no
> templates, nothing in `config.py`. This is net-new work, not a wiring task. See §5.

### 2.6 AI providers — the third dialect

`services/ai.py:39` sends everything non-Anthropic to the **OpenAI Responses API**
(`POST {base_url}/responses`). OpenRouter, DeepSeek, Qwen and OpenCode all speak
**Chat Completions** (`POST {base_url}/chat/completions`) with a different request and response
shape. This is real work, not a config entry.

**`services/ai.py`:** add `_openai_chat_completions(...)`, returning the same `Completion` dataclass.
Token counts come from `usage.prompt_tokens` / `usage.completion_tokens` instead of the Responses
API's `usage.input_tokens` / `usage.output_tokens`. Dispatch becomes a per-provider `api_style`
(`"responses"` | `"chat_completions"` | `"anthropic_messages"`) rather than the current
`if provider == "anthropic"` branch.

**`services/providers.py`:** widen `PROVIDERS` with `api_style`, `default_base_url`,
`allows_custom_base_url`, and optional `extra_headers`:

| Provider | Default base URL | API style |
|---|---|---|
| `openai` | `https://api.openai.com/v1` | `responses` |
| `anthropic` | `https://api.anthropic.com/v1` | `anthropic_messages` |
| `openrouter` | `https://openrouter.ai/api/v1` | `chat_completions` |
| `deepseek` | `https://api.deepseek.com/v1` | `chat_completions` |
| `qwen` | Alibaba DashScope compatible-mode endpoint | `chat_completions` |
| `opencode` | Operator-configured (Zen / GO gateway) | `chat_completions` |

> **Needs confirmation before coding:** the exact base URL, auth header, and model identifiers for
> **OpenCode Zen** and **OpenCode GO**, and the DashScope region endpoint for Qwen. Do not guess
> these — a wrong base URL fails at runtime with an opaque 502. The provider layer is built to be
> config-driven precisely so plugging in the confirmed values is a one-line change:
> `base_url` is stored **per credential**, and the "Test connection" button verifies it live.

Consequences to handle:
- **`ProviderCredential` gains `base_url` and `label`.** The unique constraint
  `(agency_id, provider)` becomes `(agency_id, provider, label)` so two OpenCode subscriptions
  (Zen and GO) can coexist as separate credentials.
- **OpenRouter needs `HTTP-Referer` and `X-Title` headers** for attribution; add them via
  `extra_headers`.
- **`test_provider` lists `/models`** — OpenRouter returns hundreds of entries. Cap and paginate the
  result rather than dumping it into the UI.
- **Model catalog:** `services/model_catalog.py` is a static tuple whose docstring references a
  frontend twin at `frontend/lib/model-catalog.ts` that **no longer exists**. The backend catalog is
  now the single source of truth (already exposed by `routers/catalog.py`); update the docstring and
  add entries for the new providers' economical models with their USD prices.

### 2.7 BYOK credential resolution

`services/providers.py::resolve_agent_credentials()` resolves keys from `provider_credentials` by
**agency**. With BYOK it must check the client first:

```
resolve_agent_credentials(db, agent):
    client = agent.client
    if client.billing_mode == "byok" and client.encrypted_byok_api_key:
        return (client.byok_base_url or default_for(client.byok_provider),
                decrypt_secret(client.encrypted_byok_api_key))
    return resolve_provider_credentials(db, agent.agency_id, agent.provider)
```

BYOK usage is still written to `usage_records` (with `cost_usd` = the client's own spend, useful for
reporting) but is never quota-gated.

### 2.8 Finance endpoints

**`GET /api/dashboard/finance`** — superadmin only:

```
{ period: {start, end},
  totals: { clients_active, projected_revenue_mxn, ai_cost_mxn, margin_mxn, margin_pct,
            tokens_in, tokens_out, unpriced_usage_records },
  by_seller: [ {user_id, name, clients, projected_revenue_mxn, ai_cost_mxn, margin_mxn} ],
  by_client: [ {client_id, name, seller, billing_mode, monthly_fee_mxn,
                tokens_used, monthly_token_limit, usage_pct, ai_cost_mxn, margin_mxn,
                cycle_start, cycle_end, quota_blocked} ],
  by_model:  [ {provider, model, tokens_in, tokens_out, cost_mxn} ],
  fx: {usd_to_mxn, rate_date, source} }
```

Revenue is **projected**: `SUM(monthly_fee_mxn)` over active clients for `plan` and `byok`; for
`pay_as_you_go` it is `ai_cost * (1 + markup)`. Every response is explicitly labeled as a projection
in the UI — accounting owns actual invoicing and payment records.

**`GET /api/dashboard/finance/me`** — seller-scoped version of the same shape, limited to the
caller's portfolio, with cost/margin included so a seller can see their own book.

**`GET /api/clients/{id}/usage`** — cycle window, tokens used vs. limit, percentage, daily series.
Seller-scoped; also backs the portal progress bar.

**`GET|POST /api/model-prices`** — superadmin only. `POST` **inserts a new version** with
`effective_from`; there is no update or delete. The UI states plainly that existing records keep
their original price.

### 2.9 Migration (`apps/api/migrations/versions/0018_billing_and_seller_scoping.py`)

Single migration, in order:
1. Add `Client` columns (all nullable or with `server_default`).
2. Backfill `owner_user_id` = seed superadmin id; `billing_anchor_day` = `EXTRACT(day FROM created_at)`.
3. Create `model_prices`, `fx_rates`.
4. Add `UsageRecord` columns as **nullable**, backfill `client_id` from `agents.client_id`
   (rows whose agent was already deleted get flagged `price_source="unknown"`), then set
   `client_id NOT NULL`.
5. Add index `ix_usage_records_client_created` on `(client_id, created_at)`.
6. Add `provider_credentials.base_url` / `.label`; drop and recreate the unique constraint.
7. Upgrade the seed user's `role` from `"admin"` to `"superadmin"`.

Seed `model_prices` from the static catalog in a separate idempotent data step, not in the schema
migration.

---

## 3. Local environment — remove the SQLite shortcut

The current uncommitted diff adds `Base.metadata.create_all(bind=engine)` at `apps/api/app/main.py:31`
and SQLite `connect_args` in `database.py`. **This must be reverted before the billing work starts.**

- `create_all()` **bypasses Alembic**: locally the schema is built by SQLAlchemy, in production by
  migrations. They diverge silently, and a migration bug is only discovered in production.
- SQLite and PostgreSQL disagree exactly where this plan operates: `UUID`, `Numeric` precision,
  `JSON`, timezone-aware `DateTime`, and `server_default="false"`.

Actions:
1. Remove `create_all()` from `main.py`; keep `seed_superadmin()` (which runs after
   `alembic upgrade head`).
2. Revert the SQLite `connect_args` in `database.py`.
3. Use the Postgres stack that already exists: `make up` / `make migrate`.
4. Delete the untracked `nexacore.db` and `apps/api/nexacore.db`, and add `*.db` to `.gitignore`.

---

## 4. Frontend (`apps/web`)

Every string goes through the typed i18n system. `apps/web/lib/i18n/en.ts` is the source of truth
and `es.ts` is typed as `Dictionary`, so a missing Spanish key is a **compile error**. Two new
dictionary modules under `lib/i18n/dicts/`: `finance.ts` and `billing.ts`, registered in both
`en.ts` and `es.ts`.

### 4.1 New views

| Route | Audience | Content |
|---|---|---|
| `/finance` | superadmin | Consolidated projection: revenue / AI cost / margin cards (MXN), margin % trend, per-seller table (Edgar vs. Enedina), per-client table with usage bar and cycle dates, per-model cost table, FX rate and date in the footer, "unpriced usage" warning banner. |
| `/finance/me` | seller | Same layout, scoped to the caller's portfolio. Reached from the same nav entry — the API decides scope, the UI does not branch on role for data. |
| `/settings/model-prices` | superadmin | Price table per provider/model with `effective_from`; "New price version" form. Prior versions are listed read-only with a note that historical records are unaffected. |
| `/settings/providers` | superadmin | Extended: add credential per provider with editable `base_url` and `label` (so OpenCode Zen and OpenCode GO are two entries), "Test connection" button, capped model list. |

### 4.2 Modified views

| Route | Change |
|---|---|
| `/clients/new` | New **Billing** step: billing mode selector (plan / pay-as-you-go / BYOK), monthly fee in MXN, token limit with presets ($200 / 500k, $500 / 1.5M, unlimited), cycle-day preview ("cuts on the 12th of each month"). BYOK reveals provider + base URL + API key fields. |
| `/clients/[id]` | Billing panel: current cycle window, token progress bar, tokens used vs. limit, estimated AI cost and margin (**superadmin only** — sellers see consumption, not NexaCore's cost basis), owning seller, quota state with the timestamp it engaged. |
| `/clients` | Columns for plan, usage %, and cycle end. Visual state for blocked clients. For superadmin, a seller filter. |
| `/` (home dashboard) | Superadmin gets revenue/cost/margin cards; sellers get portfolio consumption without cost basis. |
| `/portal/[slug]` | **Token progress bar** for the cycle (e.g. "150,000 / 500,000"), cycle end date, KPI cards (chats handled, AI vs. manual messages), and a BYOK-only API key field. Nothing about model, prompt, or provider configuration. |
| `components/app-shell.tsx` | New "Finance" nav entry, rendered only for roles that have it. Nav visibility is cosmetic — **authorization is enforced server-side**. |

### 4.3 Shared components

- `components/usage-bar.tsx` — token progress bar with thresholds (neutral / amber ≥80% / red at limit).
- `components/money.tsx` — MXN formatting via `Intl.NumberFormat("es-MX", {currency:"MXN"})`, with USD for cost basis where relevant.
- `lib/api.ts` — typed client methods for the new endpoints; no new fetch wrapper.

### 4.4 Role in the frontend session

`GET /api/auth/me` must return `role` so the shell can hide what the user cannot use. This is
presentation only; every endpoint independently enforces its own scope.

---

## 5. Email notifications (net-new)

Nothing exists today. Minimum viable, provider-agnostic:

- `apps/api/app/services/mailer.py` — SMTP via `aiosmtplib`, with a no-op backend when unconfigured
  so local and test runs never send mail.
- `config.py`: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_tls`,
  `emails_enabled` (default `false`).
- Two templates, in Spanish (end-user facing, like the LLM system prompt exception):
  quota warning at 80%, quota exhausted at 100%.
- Recipients: the client's `portal_email`, with the owning seller and superadmin copied.
- Idempotency via `quota_warned_at` / `quota_blocked_at` — one email per threshold per cycle, even if
  a hundred messages arrive after the limit.

---

## 6. Testing

### 6.1 pytest (`apps/api/tests`) — authorization and billing correctness

Authorization and money are tested here, not in the browser: these tests are fast, deterministic, and
run per endpoint.

- `test_scoping.py` — for **every** router listed in §2.1: Enedina gets 404 on Edgar's client,
  agents, conversations, channels, tools, and portal config; superadmin gets 200. A parametrized
  matrix, so a new endpoint that forgets scoping fails the suite.
- `test_pricing.py` — a price inserted with a later `effective_from` **does not change** the
  `cost_usd` of records written before it. This is decision #2 and it gets its own explicit test.
- `test_billing_cycle.py` — anchor day 12 → window is the 12th to the 12th; anchor 31 in February;
  cycle boundaries across a year change.
- `test_quota.py` — block at the limit; `mode` flips to `"human"`; BYOK and unlimited never block;
  `source="playground"` does not consume quota; the warning email fires once per cycle.
- `test_finance.py` — projected revenue, cost, and per-seller margin against fixture data.
- `test_usage_attribution.py` — deleting an agent preserves the client's usage history; tool-loop
  calls are metered.

The AI provider is mocked at the `chat_completion` boundary — no real tokens are ever spent in CI.

### 6.2 Playwright (`apps/web/e2e`) — user journeys

Not installed today. Setup required: `@playwright/test`, config, a deterministic seed script, and a
mock AI provider (an OpenAI-compatible stub returning fixed token counts).

- **E1 — Provider setup.** Superadmin registers an OpenRouter/OpenCode credential with a custom base
  URL and runs "Test connection".
- **E2 — Client with a token plan.** Edgar registers "Consultorio Dental Sonrisas" on the $200 MXN /
  500k plan; the cycle-day preview matches the signup day.
- **E3 — Portfolio isolation.** Enedina cannot see or reach the client (list and direct URL);
  Nicolás sees it and its $200 MXN projection in `/finance`.
- **E4 — Consumption and portal indicators.** Simulated chats consume tokens; the portal progress bar
  and KPI cards update.
- **E5 — Client cannot reconfigure the AI.** No model/prompt/provider controls in the portal, and the
  corresponding API calls are rejected.
- **E6 — Hard block.** Consumption past the limit stops AI replies, flips the conversation to
  `human`, flags it in the inbox, and shows the blocked state in `/clients`.

---

## 7. Phases (ordered by dependency)

Status: ✅ done · 🟡 partial · ⬜ not started.

| # | Phase | Status | Delivers | Depends on |
|---|---|---|---|---|
| 1 | **Revert the SQLite shortcut**, Postgres local via `make up` | ⬜ | Trustworthy migrations | — |
| 2 | **Roles + seller scoping** | 🟡 `deps.require_superadmin`/`is_superadmin` and `clients.py` scoping done, with 18 pytest cases + 10 Playwright cases green. **Still open: the other routers** (agents, conversations, whatsapp, whatsapp_cloud, agent_tools, portal) filter by `agency_id` only, so a seller still reaches another seller's agents and conversations. | The security boundary | 1 |
| 3 | **Billing data model** | 🟡 `Client` billing columns, `usage_records.client_id` + `source`, `provider_credentials.base_url` and migration `0018` written. **Still open: `model_prices`, `fx_rates`** and the cost/FX snapshot columns. | Auditable schema | 2 |
| 4 | **Pricing + FX + cycle services** with cost snapshotting; `record_usage` rewritten | 🟡 `services/billing.py` (cycle window + derived quota status) done. **Still open: `pricing.py`, `fx.py`** and the snapshot into `record_usage`. | Correct, immutable cost accounting | 3 |
| 5 | **Quota enforcement**: `quota.py`, gate at all four call sites, per-channel behavior | ⬜ status is computed and exposed, but nothing blocks a reply yet | Hard limits | 4 |
| 6 | **Email notifications**: mailer, config, templates, thresholds | ⬜ | Client is informed on block | 5 |
| 7 | **`chat_completions` dialect** + OpenRouter / DeepSeek / Qwen / OpenCode; per-credential `base_url` | ✅ dialect in `ai.py`, six providers registered, `base_url` per credential, and "Test connection" now validates against the configured endpoint instead of the provider default. **Still to confirm: the real OpenCode Zen / GO endpoints and the Qwen region** (§8). | Cheap providers, better margin | 3 |
| 8 | **Finance endpoints**: `/finance`, `/finance/me`, `/clients/{id}/usage`, `/model-prices` | 🟡 `/dashboard/finance` (projection per seller) done. **Still open: `/finance/me`, `/clients/{id}/usage`, `/model-prices`**, and cost/margin, which need phase 4. | Superadmin visibility | 4, 7 |
| 9 | **Frontend**: new + modified views, i18n `finance` / `billing` dictionaries, shared components | 🟡 `/finance`, `/settings/team`, billing fields on client create/edit, token usage bar, all six providers with a base-URL field, role-aware nav, `finance` dictionary in EN/ES. Typecheck, lint and build pass. **Still open: the client portal token bar and KPIs**, and cost/margin columns (need phase 4). | The whole thing is usable | 8 |
| 10 | **Playwright E2E** E1–E6 | 🟡 E2, E3, E5 (partly) covered by `tests/e2e_finance_and_roles_test.ts`, 10 cases green. **Still open: E1 (provider setup), E4 (consumption + portal bar), E6 (hard block)** — all blocked on phases 5, 7 and 9. | Journey coverage | 9 |
| 11 | **Deploy**: push, Dokploy VPS, `alembic upgrade head`, price + FX seed, verify | ⬜ | Production | 10 |

Phases 2 and 7 are independent of each other and can run in parallel once phase 3's migration lands.

---

## 8. Open items to confirm before coding

1. **OpenCode Zen / GO**: base URL, auth header, and model identifiers. Same for the Qwen DashScope
   region endpoint. Needed for phase 7 — everything else is already config-driven.
2. **Banxico SIE token** for the FIX series, plus the `fx_fallback_usd_mxn` seed value.
3. **Pay-as-you-go markup**: fixed percentage, or per client? Affects the `Client` schema in phase 3.
4. **Plan presets**: confirm the tiers to ship ($200 / 500k, $500 / 1.5M, unlimited?) and whether a
   seller may set an arbitrary fee or must pick a preset.
5. **SMTP credentials** for the notification sender (phase 6).
