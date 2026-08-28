from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parents[1]   # apps/api
REPO_ROOT = Path(__file__).resolve().parents[3]  # monorepo root (used for a shared local .env)


class Settings(BaseSettings):
    app_name: str = "NexaCoreAgentManager API"
    database_url: str = "postgresql+psycopg://nexacore:nexacore@localhost:5432/nexacore"
    secret_key: str = "dev-local-change-this-key-please"
    encryption_key: str = "dev-local-change-this-key-too"
    frontend_url: str = "http://localhost:3000"
    access_token_minutes: int = 60 * 24 * 7
    # Session cookie flags. Defaults suit local HTTP; set cookie_secure=true (and
    # cookie_samesite=none when the frontend and API are on different sites)
    # behind HTTPS in production.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    # Rate limiting on public/unauthenticated endpoints (per client IP). Disable
    # only for tests or when a proxy in front already enforces limits.
    rate_limit_enabled: bool = True
    # SSRF guard for agent HTTP tools: URLs resolving to private/loopback
    # addresses are rejected. Enable only on self-hosted deployments that need
    # tools to reach internal services.
    tools_allow_private_urls: bool = False
    storage_dir: Path = APP_DIR / "storage"
    backend_url: str = "http://localhost:8000"
    whatsapp_bridge_url: str = "http://localhost:3101"
    whatsapp_bridge_token: str = "dev-local-change-this-bridge-token"
    # Meta Graph API root used by the WhatsApp Cloud API channel; override to
    # point at a mock server in tests.
    meta_graph_base_url: str = "https://graph.facebook.com/v23.0"
    # Banco de Mexico SIE token for the USD/MXN FIX series. Without it the FX
    # service falls back to the last stored rate, then to the seed below.
    banxico_token: str = ""
    fx_fallback_usd_mxn: float = 17.0
    # Daily FX refresh + model-catalog drift report. Disable on all but one
    # replica when running more than one API process.
    daily_jobs_enabled: bool = True
    # Bootstrap data from app/seeds/*.json applied on startup (agency, users,
    # clients, agents). Create-only: existing records are never overwritten.
    seed_enabled: bool = True
    # Re-apply the seeded roles and password hashes to already-seeded users on
    # every start. Off so a password changed in the UI survives a restart; turn
    # it on temporarily to recover a locked-out superadmin.
    seed_reset_passwords: bool = False
    # Directory holding the seed files. Point it at a path outside the repo
    # (a mounted volume) to keep private bootstrap data out of version control.
    seed_dir: str = ""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", APP_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
