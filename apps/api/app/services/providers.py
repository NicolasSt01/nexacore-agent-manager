"""Supported AI providers (bring your own key, one per agency)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Agent, ProviderCredential
from ..security import decrypt_secret


# `pool` marks a subscription gateway: it meters one shared allowance instead of
# billing per token, and exposes it at {base_url}/usage. Those providers need
# the circuit breaker in services/subscription.py — metered providers do not.
PROVIDERS: dict[str, dict] = {
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1"},
    "anthropic": {"label": "Anthropic", "base_url": "https://api.anthropic.com/v1"},
    "openrouter": {"label": "OpenRouter (DeepSeek / Qwen / Llama)", "base_url": "https://openrouter.ai/api/v1"},
    # Verified live against the account's key: api.opencode.ai answers 200 with
    # a "Not Found" body, which looks healthy but is not the API.
    "opencode": {"label": "OpenCode Zen", "base_url": "https://opencode.ai/zen/v1", "pool": True},
    "opencode_go": {"label": "OpenCode GO", "base_url": "https://opencode.ai/zen/go/v1", "pool": True},
    "deepseek": {"label": "DeepSeek Direct", "base_url": "https://api.deepseek.com/v1"},
    "qwen": {"label": "Qwen / DashScope", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
}
SUPPORTED = tuple(PROVIDERS)


def has_shared_pool(provider: str) -> bool:
    """Whether this provider meters a shared subscription pool."""
    return bool(PROVIDERS.get(provider, {}).get("pool"))


def base_url_for(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("base_url", "https://api.openai.com/v1")


def resolve_provider_credentials(db: Session, agency_id, provider: str) -> tuple[str, str] | None:
    """(base_url, api_key) for an agency's provider key, or None if unknown or unset."""
    if provider not in PROVIDERS:
        return None
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.agency_id == agency_id,
            ProviderCredential.provider == provider,
        )
    )
    if not credential:
        return None
    base_url = credential.base_url or base_url_for(provider)
    return base_url, decrypt_secret(credential.encrypted_api_key)


def resolve_agent_credentials(db: Session, agent: Agent) -> tuple[str, str] | None:
    """(base_url, api_key) for the agent's provider using the agency's stored key."""
    return resolve_provider_credentials(db, agent.agency_id, agent.provider)
