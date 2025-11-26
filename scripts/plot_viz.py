"""
Generate simple PNG plots from debates summaries.
Requires: pandas, seaborn, matplotlib.
Run: python scripts/plot_viz.py --viz-dir results/viz --out-dir results/plots
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np


def plot_winner_counts(viz_dir: Path, out_dir: Path):
    df = pd.read_csv(viz_dir / "winner_counts.csv")
    sns.set_theme(style="whitegrid")
    ax = sns.barplot(x="winner", y="count", data=df, palette="muted")
    ax.set_title("Winner Distribution")
    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / "winner_counts.png")
    plt.close()


def plot_topic_winrates(viz_dir: Path, out_dir: Path):
    df = pd.read_csv(viz_dir / "topic_winrate.csv")
    df = df.set_index("topic_id")[["pro_wins", "con_wins", "ties"]]
    ax = df.plot(kind="bar", stacked=True, figsize=(8, 4), color=["#4c72b0", "#c44e52", "#55a868"])
    ax.set_ylabel("Count")
    ax.set_title("Wins by Topic")
    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / "topic_winrate.png")
    plt.close()


def plot_model_dimension_heatmap(viz_dir: Path, out_dir: Path):
    df = pd.read_csv(viz_dir / "model_dimension_avg.csv")
    pivot = df.pivot(index="model_id", columns="dimension", values="mean_score")
    plt.figure(figsize=(6, 3 + 0.4 * len(pivot)))
    ax = sns.heatmap(pivot, annot=True, fmt=".2f", cmap="YlGnBu")
    ax.set_title("Per-Model Dimension Averages")
    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / "model_dimension_heatmap.png")
    plt.close()


def plot_judge_agreement(viz_dir: Path, out_dir: Path):
    df = pd.read_csv(viz_dir / "judge_agreement.csv")
    judges = sorted(set(df.judge_a).union(df.judge_b))
    mat = pd.DataFrame(np.ones((len(judges), len(judges))), index=judges, columns=judges)
    for _, row in df.iterrows():
        mat.loc[row.judge_a, row.judge_b] = row.agreement_rate
        mat.loc[row.judge_b, row.judge_a] = row.agreement_rate
    plt.figure(figsize=(4 + 0.4 * len(judges), 4 + 0.4 * len(judges)))
    ax = sns.heatmap(mat, annot=True, fmt=".2f", cmap="Blues", vmin=0, vmax=1)
    ax.set_title("Judge Winner Agreement")
    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / "judge_agreement.png")
    plt.close()


def plot_judge_alignment(viz_dir: Path, out_dir: Path):
    df = pd.read_csv(viz_dir / "judge_majority_alignment.csv")
    sns.set_theme(style="whitegrid")
    ax = sns.barplot(x="judge_id", y="alignment_rate", data=df, palette="crest")
    ax.set_title("Judge vs Panel Majority")
    ax.set_ylabel("Alignment rate")
    ax.set_ylim(0, 1)
    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / "judge_majority_alignment.png")
    plt.close()


def plot_model_side_winrate(viz_dir: Path, out_dir: Path):
    df = pd.read_csv(viz_dir / "model_winrate_by_side.csv")
    rows = []
    for _, r in df.iterrows():
        rows.append({"model_id": r.model_id, "side": "pro", "wins": r.pro_w, "losses": r.pro_l, "ties": r.pro_t})
        rows.append({"model_id": r.model_id, "side": "con", "wins": r.con_w, "losses": r.con_l, "ties": r.con_t})
    melt = pd.DataFrame(rows)
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(8, 4 + 0.3*len(df)))
    ax = sns.barplot(x="wins", y="model_id", hue="side", data=melt, orient="h")
    ax.set_title("Wins by Side per Model")
    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / "model_winrate_by_side.png")
    plt.close()


def plot_dimension_gaps(viz_dir: Path, out_dir: Path):
    df = pd.read_csv(viz_dir / "dimension_score_gaps.csv")
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(8,4))
    ax = sns.boxplot(x="dimension", y="gap", data=df, palette="vlag")
    ax.axhline(0, color="black", linewidth=1)
    ax.set_title("Score Gap (PRO minus CON) per Dimension")
    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / "dimension_score_gaps.png")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Plot debates summaries to PNGs.")
    parser.add_argument("--viz-dir", default="results/viz", help="Directory containing summary CSVs.")
    parser.add_argument("--out-dir", default="results/plots", help="Directory to write PNG plots.")
    args = parser.parse_args()

    viz_dir = Path(args.viz_dir)
    out_dir = Path(args.out_dir)

    plot_winner_counts(viz_dir, out_dir)
    plot_topic_winrates(viz_dir, out_dir)
    plot_model_dimension_heatmap(viz_dir, out_dir)
    plot_judge_agreement(viz_dir, out_dir)
    plot_judge_alignment(viz_dir, out_dir)
    plot_model_side_winrate(viz_dir, out_dir)
    plot_dimension_gaps(viz_dir, out_dir)

    print(f"Wrote plots to {out_dir}")


if __name__ == "__main__":
    main()
