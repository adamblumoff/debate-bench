"""`debatebench rate` command."""

from __future__ import annotations

from pathlib import Path

import typer

from .. import config as cfg
from ..rating import recompute_ratings
from ..storage import load_debate_records, write_ratings
from .common import console


def rate_command(
    debates_path: Path = typer.Option(
        Path("results/debates.jsonl"), help="Path to debates file."
    ),
    config_path: Path = typer.Option(
        Path("configs/config.yaml"), help="Path to main benchmark config."
    ),
    ratings_path: Path = typer.Option(
        Path("results/ratings.json"), help="Output ratings file."
    ),
):
    """
    Recompute ratings from stored debates.
    """
    main_cfg = cfg.load_main_config(config_path)
    debates = load_debate_records(debates_path)
    ratings_file = recompute_ratings(debates, main_cfg)
    write_ratings(ratings_path, ratings_file)
    console.print(f"[green]Wrote ratings to {ratings_path}")


__all__ = ["rate_command"]
