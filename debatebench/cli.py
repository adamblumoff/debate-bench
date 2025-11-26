"""
CLI entrypoints for DebateBench.
"""
from __future__ import annotations

import itertools
import random
import time
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
from .settings import load_settings
from collections import defaultdict
import csv
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

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
        Path("results/debates.jsonl"), help="Base output debates file (overridden/auto-suffixed by run tag)."
    ),
    run_tag: Optional[str] = typer.Option(
        None,
        help="If set, writes debates to results/debates_<run_tag>.jsonl (and leaves the default file untouched).",
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
        False, help="Randomly swap Pro/Con assignment per debate (ignored if --balanced-sides)."
    ),
    balanced_sides: bool = typer.Option(
        True, help="Ensure each model pair plays both sides."
    ),
):
    """
    Run a batch of debates and append results.
    """
    main_cfg, topics, debater_models, judge_models = cfg.load_all_configs(
        config_path, topics_path, models_path, judges_path
    )

    # derive run tag and output paths
    if not run_tag:
        run_tag = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
    debates_path = debates_path.parent / f"debates_{run_tag}.jsonl"
    viz_dir = Path("results") / f"viz_{run_tag}"
    plots_dir = Path("results") / f"plots_{run_tag}"

    if not topics:
        raise typer.BadParameter("Topics list is empty.")
    if len(judge_models) < main_cfg.num_judges:
        raise typer.BadParameter(
            f"Judge pool ({len(judge_models)}) smaller than required panel ({main_cfg.num_judges})."
        )
    if len(debater_models) < 2:
        raise typer.BadParameter("Need at least two debater models.")
    overlap = {m.id for m in debater_models}.intersection({j.id for j in judge_models})
    if overlap:
        raise typer.BadParameter(
            f"Judge pool must not include evaluated debater ids; overlap: {', '.join(sorted(overlap))}"
        )

    rng = random.Random(seed)
    settings = load_settings()

    topics_selected = topics
    if sample_topics is not None:
        if sample_topics <= 0:
            raise typer.BadParameter("sample_topics must be positive.")
        topics_selected = rng.sample(topics, k=min(sample_topics, len(topics)))

    # Build adapters
    debater_adapters = {m.id: build_debater_adapter(m, settings) for m in debater_models}
    judge_adapters = {j.id: build_judge_adapter(j, settings) for j in judge_models}

    # Generate schedule of model pairs
    if balanced_sides:
        pairs = list(itertools.permutations(debater_models, 2))
    else:
        pairs = list(itertools.combinations(debater_models, 2))
    total_runs = len(pairs) * len(topics_selected) * debates_per_pair
    console.print(f"Scheduled {total_runs} debates.")

    run_index = 0
    for topic in topics_selected:
        for (model_a, model_b) in pairs:
            for rep in range(debates_per_pair):
                run_index += 1
                pro_model = model_a
                con_model = model_b
                if (not balanced_sides) and swap_sides and rng.random() < 0.5:
                    pro_model, con_model = con_model, pro_model

                pro_adapter = debater_adapters[pro_model.id]
                con_adapter = debater_adapters[con_model.id]

                console.print(
                    f"[yellow]Debate {run_index}/{total_runs}[/yellow] "
                    f"Topic '{topic.id}' | PRO={pro_model.id} vs CON={con_model.id}"
                )
                log = console.print

                try:
                    t0 = time.perf_counter()
                    transcript = run_debate(
                        topic=topic,
                        pro_adapter=pro_adapter,
                        con_adapter=con_adapter,
                        config=main_cfg,
                        seed=seed,
                        log=log,
                    )

                    judge_pool = sample_judges(
                        list(judge_models), main_cfg.num_judges, seed=rng.randint(0, 1_000_000)
                    )
                    judge_adapter_objs = [judge_adapters[j.id] for j in judge_pool]
                    console.print(
                        f"  Judging with panel: {', '.join(j.id for j in judge_pool)}"
                    )
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
                    elapsed = (time.perf_counter() - t0) * 1000

                    console.print(
                        f"[cyan]{run_index}/{total_runs}[/cyan] "
                        f"Topic '{topic.id}' {pro_model.id} (Pro) vs {con_model.id} (Con) "
                        f"-> winner: {aggregate.winner} ({elapsed:.0f} ms)"
                    )
                except Exception as e:
                    console.print(f"[red]Debate failed ({pro_model.id} vs {con_model.id} on {topic.id}): {e}")

    console.print(f"[green]Run complete. Writing summaries to {viz_dir} and plots to {plots_dir}")
    summarize(debates_path=debates_path, out_dir=viz_dir)
    plot_command(viz_dir=viz_dir, out_dir=plots_dir)


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


@app.command("summarize")
def summarize(
    debates_path: Path = typer.Option(
        Path("results/debates.jsonl"), help="Path to debates file."
    ),
    out_dir: Path = typer.Option(
        Path("results/viz"), help="Directory to write summary CSVs."
    ),
):
    """
    Generate lightweight CSV summaries from debates.jsonl:
    - winner_counts.csv (pro/con/tie totals)
    - topic_winrate.csv (wins/ties per topic)
    - model_dimension_avg.csv (per-model per-dimension averages, by side)
    - judge_agreement.csv (pairwise judge winner agreement rates)
    - model_winrate_by_side.csv (wins/losses/ties when model is PRO vs CON)
    - judge_majority_alignment.csv (% of debates where judge matches panel)
    - dimension_score_gaps.csv (mean_pro - mean_con per dimension per debate)
    - judge_latency.csv (mean latency per judge)
    - turn_timings.csv (mean turn duration per model side)
    - token_usage.csv (mean prompt/completion tokens per model side)
    """
    debates = load_debate_records(debates_path)
    if not debates:
        console.print(f"[red]No debates found at {debates_path}")
        raise typer.Exit(code=1)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Winner counts
    win_counts = defaultdict(int)
    for d in debates:
        win_counts[d.aggregate.winner] += 1
    with (out_dir / "winner_counts.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["winner", "count"])
        for k in ("pro", "con", "tie"):
            writer.writerow([k, win_counts.get(k, 0)])

    # Topic win rates
    topic_stats = defaultdict(lambda: defaultdict(int))
    for d in debates:
        t = d.transcript.topic.id
        topic_stats[t][d.aggregate.winner] += 1
    with (out_dir / "topic_winrate.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["topic_id", "pro_wins", "con_wins", "ties", "total"])
        for topic_id, stats in sorted(topic_stats.items()):
            pro = stats.get("pro", 0)
            con = stats.get("con", 0)
            tie = stats.get("tie", 0)
            total = pro + con + tie
            writer.writerow([topic_id, pro, con, tie, total])

    # Per-model per-dimension averages (by side)
    # We attribute mean_pro scores to pro_model_id, mean_con to con_model_id.
    dim_sums = defaultdict(lambda: defaultdict(float))
    dim_counts = defaultdict(lambda: defaultdict(int))
    turn_duration = defaultdict(lambda: {"pro": [], "con": []})
    token_usage = defaultdict(lambda: {"pro_prompt": [], "pro_completion": [], "con_prompt": [], "con_completion": []})
    for d in debates:
        pro_id = d.transcript.pro_model_id
        con_id = d.transcript.con_model_id
        for dim, score in d.aggregate.mean_pro.items():
            dim_sums[pro_id][dim] += score
            dim_counts[pro_id][dim] += 1
        for dim, score in d.aggregate.mean_con.items():
            dim_sums[con_id][dim] += score
            dim_counts[con_id][dim] += 1
        # accumulate timing and token usage
        for t in d.transcript.turns:
            side = "pro" if t.speaker == "pro" else "con"
            model_id = pro_id if side == "pro" else con_id
            if t.duration_ms is not None:
                turn_duration[model_id][side].append(t.duration_ms)
            if t.prompt_tokens is not None:
                key = f"{side}_prompt"
                token_usage[model_id][key].append(t.prompt_tokens)
            if t.completion_tokens is not None:
                key = f"{side}_completion"
                token_usage[model_id][key].append(t.completion_tokens)
    with (out_dir / "model_dimension_avg.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model_id", "dimension", "mean_score", "samples"])
        for model_id in sorted(dim_sums.keys()):
            for dim, total in dim_sums[model_id].items():
                cnt = dim_counts[model_id][dim]
                mean = total / cnt if cnt else 0.0
                writer.writerow([model_id, dim, f"{mean:.4f}", cnt])

    # Turn timing per model side
    with (out_dir / "turn_timings.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model_id", "side", "mean_ms", "samples"])
        for model_id, buckets in sorted(turn_duration.items()):
            for side in ("pro", "con"):
                arr = buckets[side]
                mean = sum(arr) / len(arr) if arr else 0.0
                writer.writerow([model_id, side, f"{mean:.2f}", len(arr)])

    # Token usage per model side
    with (out_dir / "token_usage.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model_id", "side", "mean_prompt_tokens", "mean_completion_tokens", "samples"])
        for model_id, buckets in sorted(token_usage.items()):
            for side in ("pro", "con"):
                pkey = f"{side}_prompt"
                ckey = f"{side}_completion"
                pvals = buckets[pkey]
                cvals = buckets[ckey]
                cnt = max(len(pvals), len(cvals), 0)
                mp = sum(pvals) / len(pvals) if pvals else 0.0
                mc = sum(cvals) / len(cvals) if cvals else 0.0
                writer.writerow([model_id, side, f"{mp:.2f}", f"{mc:.2f}", cnt])

    # Judge agreement matrix (winner label agreement)
    pair_agree = defaultdict(int)
    pair_total = defaultdict(int)
    judge_match_majority = defaultdict(int)
    judge_total = defaultdict(int)
    for d in debates:
        winners = {j.judge_id: j.winner for j in d.judges}
        ids = list(winners.keys())
        majority = d.aggregate.winner
        for j_id, win in winners.items():
            judge_total[j_id] += 1
            if win == majority:
                judge_match_majority[j_id] += 1
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                pair_total[(a, b)] += 1
                if winners[a] == winners[b]:
                    pair_agree[(a, b)] += 1
    with (out_dir / "judge_agreement.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["judge_a", "judge_b", "agree", "total", "agreement_rate"])
        for (a, b), tot in sorted(pair_total.items()):
            agree = pair_agree.get((a, b), 0)
            rate = agree / tot if tot else 0.0
            writer.writerow([a, b, agree, tot, f"{rate:.4f}"])

    # Judge majority alignment
    with (out_dir / "judge_majority_alignment.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["judge_id", "matches_majority", "total", "alignment_rate"])
        for j_id, tot in sorted(judge_total.items()):
            match = judge_match_majority.get(j_id, 0)
            rate = match / tot if tot else 0.0
            writer.writerow([j_id, match, tot, f"{rate:.4f}"])

    # Model winrate by side
    side_stats = defaultdict(lambda: {"pro_w":0,"pro_l":0,"pro_t":0,"con_w":0,"con_l":0,"con_t":0})
    for d in debates:
        pro = d.transcript.pro_model_id
        con = d.transcript.con_model_id
        winner = d.aggregate.winner
        if winner == "pro":
            side_stats[pro]["pro_w"] += 1
            side_stats[con]["con_l"] += 1
        elif winner == "con":
            side_stats[pro]["pro_l"] += 1
            side_stats[con]["con_w"] += 1
        else:
            side_stats[pro]["pro_t"] += 1
            side_stats[con]["con_t"] += 1
    with (out_dir / "model_winrate_by_side.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model_id","pro_w","pro_l","pro_t","con_w","con_l","con_t"])
        for m_id, stats in sorted(side_stats.items()):
            writer.writerow([m_id, stats["pro_w"], stats["pro_l"], stats["pro_t"], stats["con_w"], stats["con_l"], stats["con_t"]])

    # Dimension score gaps per debate (mean_pro - mean_con)
    with (out_dir / "dimension_score_gaps.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["debate_id", "dimension", "gap"])
        for d in debates:
            for dim, pro_score in d.aggregate.mean_pro.items():
                con_score = d.aggregate.mean_con.get(dim, 0.0)
                writer.writerow([d.transcript.debate_id, dim, pro_score - con_score])

    console.print(f"[green]Wrote summaries to {out_dir}")


@app.command("plot")
def plot_command(
    viz_dir: Path = typer.Option(Path("results/viz"), help="Directory with summary CSVs (from summarize)."),
    out_dir: Path = typer.Option(Path("results/plots"), help="Directory to write PNG plots."),
):
    """
    Generate PNG plots from summary CSVs (requires pandas, seaborn, matplotlib).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(out_dir / name, bbox_inches="tight")
        plt.close(fig)

    # Winner counts
    df = pd.read_csv(viz_dir / "winner_counts.csv")
    fig, ax = plt.subplots()
    sns.barplot(x="winner", y="count", data=df, palette="muted", ax=ax)
    ax.set_title("Winner Distribution")
    save(fig, "winner_counts.png")

    # Topic win rates
    df = pd.read_csv(viz_dir / "topic_winrate.csv").set_index("topic_id")[["pro_wins", "con_wins", "ties"]]
    fig, ax = plt.subplots(figsize=(8, 4))
    df.plot(kind="bar", stacked=True, ax=ax, color=["#4c72b0", "#c44e52", "#55a868"])
    ax.set_ylabel("Count")
    ax.set_title("Wins by Topic")
    save(fig, "topic_winrate.png")

    # Model dimension heatmap
    df = pd.read_csv(viz_dir / "model_dimension_avg.csv")
    pivot = df.pivot(index="model_id", columns="dimension", values="mean_score")
    fig, ax = plt.subplots(figsize=(6, 3 + 0.4 * len(pivot)))
    sns.heatmap(pivot, annot=True, fmt=".2f", cmap="YlGnBu", ax=ax)
    ax.set_title("Per-Model Dimension Averages")
    save(fig, "model_dimension_heatmap.png")

    # Judge agreement
    df = pd.read_csv(viz_dir / "judge_agreement.csv")
    judges = sorted(set(df.judge_a).union(df.judge_b))
    mat = pd.DataFrame(1.0, index=judges, columns=judges)
    for _, row in df.iterrows():
        mat.loc[row.judge_a, row.judge_b] = row.agreement_rate
        mat.loc[row.judge_b, row.judge_a] = row.agreement_rate
    fig, ax = plt.subplots(figsize=(4 + 0.4 * len(judges), 4 + 0.4 * len(judges)))
    sns.heatmap(mat, annot=True, fmt=".2f", cmap="Blues", vmin=0, vmax=1, ax=ax)
    ax.set_title("Judge Winner Agreement")
    save(fig, "judge_agreement.png")

    # Judge majority alignment
    df = pd.read_csv(viz_dir / "judge_majority_alignment.csv")
    fig, ax = plt.subplots()
    sns.barplot(x="judge_id", y="alignment_rate", data=df, palette="crest", ax=ax)
    ax.set_title("Judge vs Panel Majority")
    ax.set_ylim(0, 1)
    save(fig, "judge_majority_alignment.png")

    # Model winrate by side
    df = pd.read_csv(viz_dir / "model_winrate_by_side.csv")
    rows = []
    for _, r in df.iterrows():
        rows.append({"model_id": r.model_id, "side": "pro", "wins": r.pro_w})
        rows.append({"model_id": r.model_id, "side": "con", "wins": r.con_w})
    melt = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(8, 4 + 0.3 * len(df)))
    sns.barplot(x="wins", y="model_id", hue="side", data=melt, orient="h", ax=ax)
    ax.set_title("Wins by Side per Model")
    save(fig, "model_winrate_by_side.png")

    # Dimension score gaps
    df = pd.read_csv(viz_dir / "dimension_score_gaps.csv")
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.boxplot(x="dimension", y="gap", data=df, palette="vlag", ax=ax)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_title("Score Gap (PRO minus CON) per Dimension")
    save(fig, "dimension_score_gaps.png")

    # Turn timings
    df = pd.read_csv(viz_dir / "turn_timings.csv")
    fig, ax = plt.subplots(figsize=(8, 4 + 0.2 * len(df)))
    sns.barplot(x="mean_ms", y="model_id", hue="side", data=df, orient="h", ax=ax)
    ax.set_title("Mean Turn Duration (ms) by Model and Side")
    save(fig, "turn_timings.png")

    # Token usage
    df = pd.read_csv(viz_dir / "token_usage.csv")
    melt = df.melt(id_vars=["model_id", "side"], value_vars=["mean_prompt_tokens", "mean_completion_tokens"], var_name="kind", value_name="tokens")
    fig, ax = plt.subplots(figsize=(8, 4 + 0.2 * len(df)))
    sns.barplot(x="tokens", y="model_id", hue="kind", data=melt, orient="h", ax=ax)
    ax.set_title("Mean Token Usage by Model and Side")
    save(fig, "token_usage.png")

    console.print(f"[green]Wrote plots to {out_dir}")


def main():
    app(prog_name="debatebench")


if __name__ == "__main__":
    main()
