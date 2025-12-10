"""
Environment-backed settings loader.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Settings:
    openrouter_api_key: Optional[str] = None
    openrouter_site_url: Optional[str] = None
    openrouter_site_name: Optional[str] = None
    capture_usage_costs: bool = True


def load_settings() -> Settings:
    # Load from .env if present
    load_dotenv()

    def _bool_env(name: str, default: bool = True) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openrouter_site_url=os.getenv("OPENROUTER_SITE_URL"),
        openrouter_site_name=os.getenv("OPENROUTER_SITE_NAME"),
        capture_usage_costs=_bool_env("OPENROUTER_INCLUDE_USAGE", True),
    )
