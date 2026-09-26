from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def host_name(host: str) -> str:
    """A Host value's name, lower-cased, without port or IPv6 brackets."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1 : host.index("]")] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "YouTube Win-Engine"
    app_version: str = "0.13.0"
    # Fails closed: only an explicit "development" opens the admin endpoints
    # without a token.
    app_environment: str = "production"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    bind_host: str = "127.0.0.1"
    # Host names this server answers to (comma-separated, ports ignored). A page
    # that rebinds its own domain to 127.0.0.1 sends its domain here and is
    # refused. Add the machine's LAN name or address only if bind_host exposes
    # the app beyond this computer.
    allowed_hosts: str = "127.0.0.1,localhost,::1"
    admin_api_token: str | None = None
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    rate_limit_max_requests: int = Field(default=60, ge=1)
    # Budget per route for requests that spend YouTube quota, Gemini calls or a
    # cloud round trip (analyze, research, generate, refresh, link, sync).
    analyze_rate_limit_max_requests: int = Field(default=8, ge=1)
    max_request_bytes: int = Field(default=1_048_576, ge=1024)

    youtube_api_key: str | None = None
    youtube_api_keys: str | None = None
    # search.list costs 100 units for any page size up to 50; above 50 every
    # search fails with HTTP 400.
    youtube_max_results: int = Field(default=5, ge=1, le=50)
    youtube_max_research_queries: int = 5

    cache_ttl_trending_seconds: int = 21600
    cache_ttl_evergreen_seconds: int = 604800
    redis_url: str | None = None
    redis_key_prefix: str = "win_engine"
    request_timeout_seconds: int = 10
    database_path: str = "runtime/data/win_engine.db"
    creator_timezone: str = "Asia/Kolkata"

    youtube_oauth_client_id: str | None = None
    youtube_oauth_client_secret: str | None = None
    youtube_oauth_redirect_uri: str = "http://127.0.0.1:8000/oauth/youtube/callback"
    oauth_token_encryption_key: str | None = None

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    # Tried once when the primary model is overloaded (503) or rate-limited
    # (429). Models have separate quota buckets, so this usually succeeds where
    # the local fallback writer would otherwise take over. Empty disables it.
    gemini_fallback_model: str = "gemini-3.1-flash-lite"
    gemini_timeout_seconds: float = Field(default=60.0, ge=5.0, le=300.0)
    # Retries after a timeout, network error or 5xx, and after a 429.
    gemini_transient_retries: int = Field(default=1, ge=0, le=4)
    gemini_rate_limit_retries: int = Field(default=2, ge=0, le=4)
    gemini_retry_base_seconds: float = Field(default=0.75, ge=0.1, le=10.0)
    # Longest wait before a retry. A longer Retry-After ends the attempts on
    # that model at once instead of holding the request thread for minutes.
    gemini_max_retry_wait_seconds: float = Field(default=20.0, ge=1.0, le=60.0)
    # Reasoning tokens on thinking models count against maxOutputTokens, so the
    # ceiling leaves room above what a caller sizes for the JSON alone.
    gemini_output_token_ceiling: int = Field(default=8192, ge=1024, le=32768)
    # Consecutive transient failures that pause one kind of Gemini call, and for how long.
    gemini_cooldown_failure_threshold: int = Field(default=2, ge=1, le=5)
    gemini_cooldown_seconds: float = Field(default=60.0, ge=5.0, le=900.0)
    # Allowance of one API request (gemini_client.request_budget). An analysis
    # normally makes at most seven logical calls.
    gemini_request_max_calls: int = Field(default=12, ge=1, le=50)
    gemini_request_deadline_seconds: float = Field(default=300.0, ge=30.0, le=1800.0)

    # YouTube search suggestions: the demand signal (what viewers actually
    # type). Unofficial endpoint; bounded, cached, and fail-soft.
    search_suggest_enabled: bool = True
    search_suggest_timeout_seconds: float = Field(default=3.0, ge=0.5, le=15.0)
    search_suggest_max_queries: int = Field(default=6, ge=0, le=12)

    snapshot_collector_enabled: bool = False
    snapshot_collector_dry_run: bool = False
    snapshot_collector_interval_seconds: int = Field(default=21600, ge=60)
    snapshot_collector_initial_delay_seconds: int = Field(default=30, ge=0)
    snapshot_collector_max_links_per_run: int = Field(default=3, ge=1, le=100)
    snapshot_collector_retry_base_seconds: int = Field(default=21600, ge=60)
    snapshot_collector_retry_max_seconds: int = Field(default=172800, ge=60)

    cloud_sync_enabled: bool = False
    # Stored in a VARCHAR(120) column of the cloud tables.
    cloud_sync_device_id: str | None = Field(default=None, max_length=120)
    cloud_sync_host: str | None = None
    cloud_sync_port: int = Field(default=3306, ge=1, le=65535)
    cloud_sync_database: str = "seo_yt_sync"
    cloud_sync_user: str | None = None
    cloud_sync_password: str | None = None
    cloud_sync_ssl_ca_path: str = "/run/secrets/aiven-ca.pem"
    cloud_sync_interval_seconds: int = Field(default=60, ge=30)
    cloud_sync_initial_delay_seconds: int = Field(default=10, ge=0)
    # Ceiling for the doubling wait after runs that cannot reach the cloud.
    cloud_sync_retry_max_seconds: int = Field(default=900, ge=60)

    model_config = SettingsConfigDict(env_file=".env", env_prefix="WIN_ENGINE_", extra="ignore")

    @field_validator("log_level", mode="before")
    @classmethod
    def upper_case_log_level(cls, value: object) -> object:
        # "info" names the same level as "INFO"; anything else still fails at startup.
        return value.strip().upper() if isinstance(value, str) else value

    @property
    def allowed_host_set(self) -> frozenset[str]:
        # Read like the Host header (app.request_host), so "myhost:8000" matches "myhost".
        return frozenset(host_name(host) for host in self.allowed_hosts.split(",") if host.strip())

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
