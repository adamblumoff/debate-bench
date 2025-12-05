"""Shared utilities for the DebateBench CLI.

Holds reusable console instance, option factories, and any cross-command helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console

console = Console()


def path_option(default: Path | str, help_text: str) -> Any:
    """Standardized filesystem option used across commands."""
    return typer.Option(
        default,
        help=help_text,
        dir_okay=True,
        file_okay=True,
        readable=True,
        writable=True,
    )


__all__ = ["console", "path_option"]
