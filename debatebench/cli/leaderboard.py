"""`debatebench show-leaderboard` command."""

from __future__ import annotations

from typing import Optional
from pathlib import Path

import typer
from rich.table import Table

from ..storage import read_ratings
from .common import console


def show_leaderboard(
    ratings_path: Path = typer.Option(
        Path("results/ratings.json"), help="Path to ratings file."
    ),
    top: Optional[int] = typer.Option(None, help="Show only top N."),
):
    """
    Display leaderboard from ratings file.
    """
    ratings = read_ratings(ratings_path)
    rows = sorted(ratings.models.items(), key=lambda kv: kv[1].rating, reverse=True)
    if top:
        rows = rows[:top]

    table = Table(title="DebateBench Leaderboard")
    table.add_column("Rank", justify="right")
    table.add_column("Model")
    table.add_column("Rating", justify="right")
    table.add_column("Debates", justify="right")

    # Add per-dimension columns if present
    dim_ids = set()
    for _, entry in rows:
        dim_ids.update(entry.dimension_avgs.keys())
    dim_ids = sorted(dim_ids)
    for dim in dim_ids:
        table.add_column(dim, justify="right")

    for idx, (model_id, entry) in enumerate(rows, start=1):
        cells = [
            str(idx),
            model_id,
            f"{entry.rating:.1f}",
            str(entry.games_played),
        ]
        for dim in dim_ids:
            val = entry.dimension_avgs.get(dim)
            cells.append(f"{val:.2f}" if val is not None else "-")
        table.add_row(*cells)

    console.print(table)


__all__ = ["show_leaderboard"]
