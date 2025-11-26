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
    openai_api_key: Optional[str] = None
    http_bearer_token: Optional[str] = None


def load_settings() -> Settings:
    # Load from .env if present
    load_dotenv()
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        http_bearer_token=os.getenv("HTTP_BEARER_TOKEN"),
    )
