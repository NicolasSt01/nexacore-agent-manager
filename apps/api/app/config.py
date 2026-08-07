from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parents[1]   # apps/api
REPO_ROOT = Path(__file__).resolve().parents[3]  # monorepo root (used for a shared local .env)


class Settings(BaseSettings):
    app_name: str = "OpenLivery API"
    database_url: str = "postgresql+psycopg://openlivery:openlivery@localhost:5432/openlivery"
    secret_key: str = "dev-local-change-this-key-please"
    encryption_key: str = "dev-local-change-this-key-too"
    frontend_url: str = "http://localhost:3000"
    access_token_minutes: int = 60 * 24 * 7
    storage_dir: Path = APP_DIR / "storage"
    backend_url: str = "http://localhost:8000"
    whatsapp_bridge_url: str = "http://localhost:3101"
    whatsapp_bridge_token: str = "dev-local-change-this-bridge-token"

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", APP_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
