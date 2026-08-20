# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The three services (`apps/api`, `apps/web`, `apps/whatsapp`) share a single version
and are released together.

## [Unreleased]

## [0.2.0] - 2026-08-20

Upgrading: this release adds a database migration (applied automatically by the
Docker stack; run `alembic upgrade head` on local setups) and a new backend
dependency (`pip install -r requirements.txt`).

### Added

- Custom tools for agents, configured from a new Tools tab on the agent page:
  - HTTP tools: user-defined endpoint with `{param}` path placeholders, method,
    body and query parameters, prompt instructions, optional auth headers
    (encrypted at rest) and timeout.
  - MCP servers: external servers over SSE or Streamable HTTP with optional
    auth headers. The connection must be tested (tools listed) before saving,
    and the discovered tool list is cached so chat requests never block on
    discovery.
- Tool-calling loop for both providers (OpenAI Responses API and Anthropic
  Messages API), capped per reply, with token usage summed across iterations.
  Agents without tools are unaffected.
- Tool usage recorded on each assistant reply and shown in the playground,
  including the error detail when a call fails. When a tool fails, the agent
  reports the information as unavailable instead of answering from memory.
- SSRF guard for HTTP tools: URLs resolving to private, loopback or reserved
  addresses are rejected and redirects are never followed. Self-hosted
  deployments can opt out with `TOOLS_ALLOW_PRIVATE_URLS`.
- Unread count and last-message preview on inbox conversations.
- Channel badge on inbox conversations.

### Fixed

- Spacing of stacked provider cards in settings.

### Documentation

- Full documentation site at [openlivery.com/docs](https://openlivery.com/docs) with per-feature guides in English and Spanish.
- README restructured around the documentation site, with each feature linking to its guide.
- Corrected the WhatsApp inbound route in `CLAUDE.md`.

## [0.1.0] - 2026-08-16

First tagged release.

### Added

- Multi-tenant, agency-scoped data model: agencies, users, clients, agents,
  conversations and messages, with every query isolated by `agency_id`.
- FastAPI backend with JWT auth in httpOnly cookies, SQLAlchemy models and
  Alembic migrations.
- Next.js web app: auth, dashboard, clients, agents, inbox, chat playground,
  settings, client portal and an embeddable chat widget.
- Typed i18n system (English default, Spanish) for all user-facing copy.
- WhatsApp integration through a Baileys bridge, with stateful sessions and a
  human/AI conversation mode toggle.
- AI chat over any OpenAI-compatible endpoint, with per-connection base URL and
  model configuration and connection testing.
- Knowledge documents: PDF text extraction, chunking, embedding and semantic
  retrieval assembled into the agent system prompt.
- Structured business brief for agents.
- Encryption at rest for AI API keys and WhatsApp session state.
- OpenAI and Anthropic model presets, including the GPT-5.6 family
  (`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`) and the `gpt-transcribe`
  transcription model.

### Infrastructure

- Docker Compose stack with a Makefile wrapper for build, run, migrate and test.
- Single-origin Caddy gateway (`/api/*` to the backend, everything else to the
  frontend).
- Prebuilt images published to GHCR.
- Per-IP rate limiting on public and unauthenticated endpoints.
- Custom per-client portal domains with on-demand TLS.
- README and self-hosting guide.

[Unreleased]: https://github.com/sarrazola/openlivery/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/sarrazola/openlivery/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sarrazola/openlivery/releases/tag/v0.1.0
