"""`debatebench plot` command."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import typer

from ..plot_style import apply_dark_theme, style_axes
from .common import console


def plot_command(
    viz_dir: Path = typer.Option(Path("results/viz"), help="Directory with summary CSVs (from summarize)."),
    out_dir: Path = typer.Option(Path("results/plots"), help="Directory to write PNG plots."),
):
    """
    Generate PNG plots from summary CSVs (requires pandas, seaborn, matplotlib).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    palettes = apply_dark_theme()

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(out_dir / name, bbox_inches="tight")
        plt.close(fig)

    # Winner counts
    df = pd.read_csv(viz_dir / "winner_counts.csv")
    fig, ax = plt.subplots()
    sns.barplot(x="winner", y="count", data=df, palette=palettes["seq"], ax=ax)
    ax.set_title("Winner Distribution")
    style_axes(ax)
    save(fig, "winner_counts.png")

    # Topic win rates
    df = pd.read_csv(viz_dir / "topic_winrate.csv").set_index("topic_id")[["pro_wins", "con_wins", "ties"]]
    fig, ax = plt.subplots(figsize=(8, 4))
    df.plot(kind="bar", stacked=True, ax=ax, color=palettes["seq"][:3])
    ax.set_ylabel("Count")
    ax.set_title("Wins by Topic")
    style_axes(ax)
    save(fig, "topic_winrate.png")

    # Model dimension heatmap
    df = pd.read_csv(viz_dir / "model_dimension_avg.csv")
    pivot = df.pivot(index="model_id", columns="dimension", values="mean_score")
    fig, ax = plt.subplots(figsize=(6, 3 + 0.4 * len(pivot)))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".2f",
        cmap=palettes["seq_cmap"],
        ax=ax,
        annot_kws={"color": "#e9eef7", "fontsize": 9},
    )
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
    sns.heatmap(
        mat,
        annot=True,
        fmt=".2f",
        cmap=palettes["seq_cmap"],
        vmin=0,
        vmax=1,
        ax=ax,
        annot_kws={"color": "#e9eef7", "fontsize": 9},
    )
    ax.set_title("Judge Winner Agreement")
    save(fig, "judge_agreement.png")

    # Judge majority alignment
    df = pd.read_csv(viz_dir / "judge_majority_alignment.csv")
    fig, ax = plt.subplots()
    sns.barplot(x="judge_id", y="alignment_rate", data=df, palette=palettes["seq"], ax=ax)
    ax.set_title("Judge vs Panel Majority")
    ax.set_ylim(0, 1)
    style_axes(ax)
    save(fig, "judge_majority_alignment.png")

    # Model winrate by side
    df = pd.read_csv(viz_dir / "model_winrate_by_side.csv")
    rows = []
    for _, r in df.iterrows():
        rows.append({"model_id": r.model_id, "side": "pro", "wins": r.pro_w})
        rows.append({"model_id": r.model_id, "side": "con", "wins": r.con_w})
    melt = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(8, 4 + 0.3 * len(df)))
    sns.barplot(x="wins", y="model_id", hue="side", data=melt, orient="h", ax=ax, palette=palettes["seq"])
    ax.set_title("Wins by Side per Model")
    style_axes(ax)
    save(fig, "model_winrate_by_side.png")

    # Dimension score gaps
    df = pd.read_csv(viz_dir / "dimension_score_gaps.csv")
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.boxplot(x="dimension", y="gap", data=df, palette=palettes["seq"], ax=ax)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_title("Score Gap (PRO minus CON) per Dimension")
    style_axes(ax)
    save(fig, "dimension_score_gaps.png")

    # Turn timings
    df = pd.read_csv(viz_dir / "turn_timings.csv")
    fig, ax = plt.subplots(figsize=(8, 4 + 0.2 * len(df)))
    sns.barplot(x="mean_ms", y="model_id", hue="side", data=df, orient="h", ax=ax, palette=palettes["seq"])
    ax.set_title("Mean Turn Duration (ms) by Model and Side")
    style_axes(ax)
    save(fig, "turn_timings.png")

    # Token usage
    df = pd.read_csv(viz_dir / "token_usage.csv")
    melt = df.melt(id_vars=["model_id", "side"], value_vars=["mean_prompt_tokens", "mean_completion_tokens"], var_name="kind", value_name="tokens")
    fig, ax = plt.subplots(figsize=(8, 4 + 0.2 * len(df)))
    sns.barplot(x="tokens", y="model_id", hue="kind", data=melt, orient="h", ax=ax, palette=palettes["seq"])
    ax.set_title("Mean Token Usage by Model and Side")
    style_axes(ax)
    save(fig, "token_usage.png")

    console.print(f"[green]Wrote plots to {out_dir}")


__all__ = ["plot_command"]
