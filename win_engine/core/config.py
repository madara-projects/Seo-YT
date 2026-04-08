from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "YouTube Win-Engine"
    app_version: str = "0.8.0"
    app_environment: str = "development"
    public_diagnostics_enabled: bool = True
    admin_api_token: str | None = None
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 60

    youtube_api_key: str | None = None
    youtube_api_keys: str | None = None
    youtube_max_results: int = 5

    cache_ttl_trending_seconds: int = 21600
    cache_ttl_evergreen_seconds: int = 604800
    redis_url: str | None = None
    redis_key_prefix: str = "win_engine"
    request_timeout_seconds: int = 10
    database_path: str = "win_engine.db"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="WIN_ENGINE_", extra="ignore")

    @property
    def youtube_api_key_pool(self) -> List[str]:
        raw_values = [self.youtube_api_keys, self.youtube_api_key]
        keys: List[str] = []

        for raw in raw_values:
            if not raw:
                continue
            for key in raw.split(","):
                cleaned = key.strip()
                if cleaned and cleaned not in keys:
                    keys.append(cleaned)

        return keys


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
