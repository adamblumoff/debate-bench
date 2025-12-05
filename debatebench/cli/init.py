"""`debatebench init` command."""

from __future__ import annotations

from pathlib import Path

import typer

from .. import config as cfg
from .common import console


def init_command(
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing config templates."
    ),
):
    """
    Create default config templates and results folders.
    """
    root = Path(".").resolve()
    cfg.write_default_configs(root, overwrite=force)
    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]Initialized configs/ and results/ under {root}")


__all__ = ["init_command"]
