from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "YouTube Win-Engine"
    app_version: str = "0.13.0"
    app_environment: str = "development"
    bind_host: str = "127.0.0.1"
    admin_api_token: str | None = None
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 60
    analyze_rate_limit_max_requests: int = 8

    youtube_api_key: str | None = None
    youtube_api_keys: str | None = None
    youtube_max_results: int = 5
    youtube_max_research_queries: int = 5

    cache_ttl_trending_seconds: int = 21600
    cache_ttl_evergreen_seconds: int = 604800
    redis_url: str | None = None
    redis_key_prefix: str = "win_engine"
    request_timeout_seconds: int = 10
    database_path: str = "win_engine.db"

    youtube_oauth_client_id: str | None = None
    youtube_oauth_client_secret: str | None = None
    youtube_oauth_redirect_uri: str = "http://127.0.0.1:8000/oauth/youtube/callback"
    oauth_token_encryption_key: str | None = None

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"

    snapshot_collector_enabled: bool = False
    snapshot_collector_dry_run: bool = False
    snapshot_collector_interval_seconds: int = Field(default=21600, ge=60)
    snapshot_collector_initial_delay_seconds: int = Field(default=30, ge=0)
    snapshot_collector_max_links_per_run: int = Field(default=3, ge=1, le=100)
    snapshot_collector_retry_base_seconds: int = Field(default=21600, ge=60)
    snapshot_collector_retry_max_seconds: int = Field(default=172800, ge=60)

    cloud_sync_enabled: bool = False
    cloud_sync_device_id: str | None = None
    cloud_sync_host: str | None = None
    cloud_sync_port: int = Field(default=3306, ge=1, le=65535)
    cloud_sync_database: str = "seo_yt_sync"
    cloud_sync_user: str | None = None
    cloud_sync_password: str | None = None
    cloud_sync_ssl_ca_path: str = "/run/secrets/aiven-ca.pem"
    cloud_sync_interval_seconds: int = Field(default=60, ge=30)
    cloud_sync_initial_delay_seconds: int = Field(default=10, ge=0)

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
