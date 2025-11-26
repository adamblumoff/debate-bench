"""
CLI entrypoints for DebateBench.
"""
from __future__ import annotations

import itertools
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import config as cfg
from .debate import run_debate
from .judge import run_judge_panel
from .models import build_debater_adapter, build_judge_adapter, sample_judges
from .rating import recompute_ratings
from .schema import DebateRecord
from .storage import append_debate_record, load_debate_records, read_ratings, write_ratings

app = typer.Typer(help="DebateBench CLI")
console = Console()


def _path_option(default: str, help_text: str):
    return typer.Option(default, help=help_text, dir_okay=True, file_okay=True, readable=True, writable=True)


@app.command()
def init(
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


@app.command("run")
def run_command(
    config_path: Path = typer.Option(
        Path("configs/config.yaml"),
        help="Path to main benchmark config.",
    ),
    topics_path: Path = typer.Option(
        Path("configs/topics.json"), help="Path to topics list."
    ),
    models_path: Path = typer.Option(
        Path("configs/models.yaml"), help="Path to debater models."
    ),
    judges_path: Path = typer.Option(
        Path("configs/judges.yaml"), help="Path to judge models."
    ),
    debates_path: Path = typer.Option(
        Path("results/debates.jsonl"), help="Output debates file."
    ),
    sample_topics: Optional[int] = typer.Option(
        None, help="Number of topics to sample (default all)."
    ),
    debates_per_pair: int = typer.Option(
        1, help="Number of debates per model pair per topic."
    ),
    seed: Optional[int] = typer.Option(
        None, help="Random seed for reproducibility."
    ),
    swap_sides: bool = typer.Option(
        True, help="Randomly swap Pro/Con assignment per debate."
    ),
):
    """
    Run a batch of debates and append results.
    """
    main_cfg, topics, debater_models, judge_models = cfg.load_all_configs(
        config_path, topics_path, models_path, judges_path
    )

    if not topics:
        raise typer.BadParameter("Topics list is empty.")
    if len(judge_models) < main_cfg.num_judges:
        raise typer.BadParameter(
            f"Judge pool ({len(judge_models)}) smaller than required panel ({main_cfg.num_judges})."
        )
    if len(debater_models) < 2:
        raise typer.BadParameter("Need at least two debater models.")

    rng = random.Random(seed)

    topics_selected = topics
    if sample_topics is not None:
        if sample_topics <= 0:
            raise typer.BadParameter("sample_topics must be positive.")
        topics_selected = rng.sample(topics, k=min(sample_topics, len(topics)))

    # Build adapters
    debater_adapters = {m.id: build_debater_adapter(m) for m in debater_models}
    judge_adapters = {j.id: build_judge_adapter(j) for j in judge_models}

    # Generate schedule of model pairs
    pairs = list(itertools.permutations(debater_models, 2))
    total_runs = len(pairs) * len(topics_selected) * debates_per_pair
    console.print(f"Scheduled {total_runs} debates.")

    run_index = 0
    for topic in topics_selected:
        for (model_a, model_b) in pairs:
            for rep in range(debates_per_pair):
                run_index += 1
                pro_model = model_a
                con_model = model_b
                if swap_sides and rng.random() < 0.5:
                    pro_model, con_model = con_model, pro_model

                pro_adapter = debater_adapters[pro_model.id]
                con_adapter = debater_adapters[con_model.id]

                transcript = run_debate(
                    topic=topic,
                    pro_adapter=pro_adapter,
                    con_adapter=con_adapter,
                    config=main_cfg,
                    seed=seed,
                )

                judge_pool = sample_judges(
                    list(judge_models), main_cfg.num_judges, seed=rng.randint(0, 1_000_000)
                )
                judge_adapter_objs = [judge_adapters[j.id] for j in judge_pool]
                judge_results, aggregate = run_judge_panel(
                    judge_adapter_objs, transcript, main_cfg, seed=rng.randint(0, 1_000_000)
                )

                record = DebateRecord(
                    transcript=transcript,
                    judges=judge_results,
                    aggregate=aggregate,
                    created_at=datetime.now(timezone.utc),
                )
                append_debate_record(debates_path, record)

                console.print(
                    f"[cyan]{run_index}/{total_runs}[/cyan] "
                    f"Topic '{topic.id}' {pro_model.id} (Pro) vs {con_model.id} (Con) -> winner: {aggregate.winner}"
                )


@app.command("rate")
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


@app.command("show-leaderboard")
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


@app.command("inspect-debate")
def inspect_debate(
    debate_id: str = typer.Argument(..., help="Debate ID to inspect."),
    debates_path: Path = typer.Option(
        Path("results/debates.jsonl"), help="Path to debates file."
    ),
):
    """
    Print a single debate and its judge decisions.
    """
    debates = load_debate_records(debates_path)
    matches = [d for d in debates if d.transcript.debate_id == debate_id]
    if not matches:
        console.print(f"[red]Debate {debate_id} not found.")
        raise typer.Exit(code=1)

    record = matches[0]
    console.print(f"[bold]Debate {record.transcript.debate_id}[/bold]")
    console.print(f"Motion: {record.transcript.topic.motion}")
    console.print(f"Pro: {record.transcript.pro_model_id} | Con: {record.transcript.con_model_id}")
    console.print("Transcript:")
    for turn in record.transcript.turns:
        console.print(f"  [{turn.speaker}] ({turn.stage}) {turn.content}")
    console.print("Judges:")
    for j in record.judges:
        console.print(f"  {j.judge_id}: winner={j.winner}, pro={j.pro.scores}, con={j.con.scores}")
    console.print(f"Aggregate winner: {record.aggregate.winner}")


def main():
    app(prog_name="debatebench")


if __name__ == "__main__":
    main()
