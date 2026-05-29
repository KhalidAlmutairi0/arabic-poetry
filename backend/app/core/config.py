from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────
    app_name: str = "شعر — Arabic Poetry Platform"
    app_version: str = "1.0.0"
    environment: Literal["development", "production", "testing"] = "development"
    debug: bool = False

    # ── Database ──────────────────────────────────────
    database_url: str = "postgresql+asyncpg://poetry_user:poetry_secret_123@localhost:5432/poetry_db"
    sync_database_url: str = "postgresql+psycopg://poetry_user:poetry_secret_123@localhost:5432/poetry_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        url = url.replace("sslmode=", "ssl=")
        return url

    @property
    def sync_db_url(self) -> str:
        url = self.sync_database_url or self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        for driver in ["+asyncpg", "+psycopg"]:
            url = url.replace(driver, "")
        return url

    # ── Redis ─────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Meilisearch ───────────────────────────────────
    meilisearch_url: str = ""
    meilisearch_key: str = ""

    # ── Ollama / AI ───────────────────────────────────
    ollama_url: str = "http://localhost:11434"
    ollama_model_chat: str = "qwen2.5:3b"
    ollama_model_embed: str = "nomic-embed-text"  # 274MB, 768-dim, fast
    embedding_dimensions: int = 768  # nomic-embed-text produces 768-dim vectors

    # ── Auth ──────────────────────────────────────────
    secret_key: str = "dev_secret_key_change_in_production_min_32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # ── Rate Limiting ─────────────────────────────────
    rate_limit_search: str = "60/minute"
    rate_limit_ai: str = "10/minute"
    rate_limit_default: str = "120/minute"

    # ── CORS ──────────────────────────────────────────
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://arabic-poetry-ui.vercel.app",
        "https://arabic-poetry-ui-*.vercel.app",
    ]

    # ── Cache TTLs (seconds) ──────────────────────────
    cache_ttl_search: int = 3600       # 1 hour
    cache_ttl_poet: int = 86400        # 24 hours
    cache_ttl_poem: int = 86400        # 24 hours
    cache_ttl_verse: int = 86400       # 24 hours
    cache_ttl_explanation: int = 0     # Permanent (None)
    cache_ttl_autocomplete: int = 300  # 5 minutes

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
