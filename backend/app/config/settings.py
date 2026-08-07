"""
Centralized application configuration.

All environment-driven settings live here so the rest of the codebase
never reads `os.environ` directly. Add new settings as the app grows.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    cors_origins: str = "http://localhost:5173"

    chatgpt_fetch_timeout_seconds: int = 30

    # Applies per client IP, independently to each rate-limited endpoint
    # (see app/utils/rate_limiter.py) — `/parse` and `/generate-pdf` are
    # the two that do real work per request (an external network fetch,
    # and CPU-bound HTML/LaTeX/PDF rendering), so they're the ones worth
    # bounding. 15/minute is generous for real usage (a person clicking
    # the extension's button) while still cutting off accidental loops
    # or scripted abuse well before either endpoint's actual cost adds up.
    rate_limit_per_minute: int = 15

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (avoids re-parsing env on every call)."""
    return Settings()
