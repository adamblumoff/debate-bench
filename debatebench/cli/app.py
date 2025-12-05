"""Typer application wiring for DebateBench CLI."""
from __future__ import annotations

import typer

from .init import init_command
from .run import run_command
from .rate import rate_command
from .leaderboard import show_leaderboard
from .inspect import inspect_debate
from .summarize import summarize
from .plot import plot_command
from .upload import upload_results_command

app = typer.Typer(help="DebateBench CLI")
results_app = typer.Typer(name="results", help="Results, inspection, and upload utilities.")

# Root commands
app.command("run")(run_command)
app.command("init")(init_command)
app.command("rate")(rate_command)
app.command("show-leaderboard")(show_leaderboard)
app.command("inspect-debate")(inspect_debate)
app.command("summarize")(summarize)
app.command("plot")(plot_command)
app.command("upload-results")(upload_results_command)

# Sub-app aliases (legacy flat commands remain supported)
results_app.command("rate")(rate_command)
results_app.command("show-leaderboard")(show_leaderboard)
results_app.command("inspect-debate")(inspect_debate)
results_app.command("summarize")(summarize)
results_app.command("plot")(plot_command)
results_app.command("upload-results")(upload_results_command)

app.add_typer(results_app, name="results")


def main():
    app(prog_name="debatebench")


if __name__ == "__main__":
    main()
