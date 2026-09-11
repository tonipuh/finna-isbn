"""Configuration read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Environment variable {name} must be an integer, got {raw!r}") from None


@dataclass(frozen=True)
class Settings:
    http_port: int
    finna_base_url: str
    finna_user_agent: str
    finna_language: str
    request_timeout_seconds: int
    cache_ttl_seconds: int
    cache_max_entries: int
    log_level: str

    # Build metadata (injected at container build time, see /version).
    version: str
    commit: str
    build_time: str

    @classmethod
    def from_env(cls) -> Settings:
        user_agent = os.environ.get("FINNA_USER_AGENT", "").strip()
        if not user_agent:
            raise RuntimeError(
                "FINNA_USER_AGENT is required (a descriptive User-Agent, e.g. "
                "'finna-isbn/1.0 (+https://github.com/tonipuh/finna-isbn)')"
            )
        return cls(
            http_port=_get_int("HTTP_PORT", 8080),
            finna_base_url=os.environ.get("FINNA_BASE_URL", "https://api.finna.fi/v1").rstrip("/"),
            finna_user_agent=user_agent,
            finna_language=os.environ.get("FINNA_LANGUAGE", "fin"),
            request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 10),
            cache_ttl_seconds=_get_int("CACHE_TTL_SECONDS", 86400),
            cache_max_entries=_get_int("CACHE_MAX_ENTRIES", 10000),
            log_level=os.environ.get("LOG_LEVEL", "info").lower(),
            version=os.environ.get("APP_VERSION", "dev"),
            commit=os.environ.get("APP_COMMIT", "unknown"),
            build_time=os.environ.get("APP_BUILD_TIME", "unknown"),
        )
