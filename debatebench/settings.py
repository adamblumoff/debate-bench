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


def load_settings() -> Settings:
    # Load from .env if present
    load_dotenv()
    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openrouter_site_url=os.getenv("OPENROUTER_SITE_URL"),
        openrouter_site_name=os.getenv("OPENROUTER_SITE_NAME"),
    )
