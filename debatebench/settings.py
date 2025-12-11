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
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None
    aws_profile: Optional[str] = None
    s3_region: Optional[str] = None
    s3_endpoint: Optional[str] = None
    s3_force_path_style: Optional[bool] = None


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
        s3_bucket=os.getenv("DEBATEBENCH_S3_BUCKET") or os.getenv("S3_BUCKET") or "debatebench-results",
        s3_prefix=os.getenv("DEBATEBENCH_S3_PREFIX") or os.getenv("S3_PREFIX"),
        aws_profile=os.getenv("DEBATEBENCH_AWS_PROFILE") or os.getenv("AWS_PROFILE"),
        s3_region=os.getenv("DEBATEBENCH_S3_REGION") or os.getenv("S3_REGION"),
        s3_endpoint=(
            os.getenv("DEBATEBENCH_S3_ENDPOINT")
            or os.getenv("S3_ENDPOINT")
            or os.getenv("AWS_S3_ENDPOINT")
        ),
        s3_force_path_style=(
            _bool_env("DEBATEBENCH_S3_FORCE_PATH_STYLE", False)
            if os.getenv("DEBATEBENCH_S3_FORCE_PATH_STYLE") is not None
            else (
                _bool_env("S3_FORCE_PATH_STYLE", False)
                if os.getenv("S3_FORCE_PATH_STYLE") is not None
                else None
            )
        ),
    )
