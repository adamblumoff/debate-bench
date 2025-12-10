"""Post-run aggregation for the `debatebench run` command."""
from __future__ import annotations

from ..common import console
from ..leaderboard import show_leaderboard
from ..plot import plot_command
from ..rate import rate_command
from ..summarize import summarize
from .types import RunSetup


def run_postrun(setup: RunSetup) -> None:
    """Generate summaries/plots and optional ratings/leaderboard."""
    opts = setup.options
    console.print(f"[green]Run complete. Writing summaries to {setup.viz_dir} and plots to {setup.plots_dir}")
    summarize(debates_path=setup.debates_path, out_dir=setup.viz_dir)
    plot_command(viz_dir=setup.viz_dir, out_dir=setup.plots_dir)
    if opts.postrate:
        console.print(f"[cyan]Recomputing ratings and showing leaderboard (top 10).[/cyan]")
        rate_command(debates_path=setup.debates_path, config_path=opts.config_path, ratings_path=setup.ratings_path)
        show_leaderboard(ratings_path=setup.ratings_path, top=10)


__all__ = ["run_postrun"]
