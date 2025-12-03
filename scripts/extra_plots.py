"""Generate richer comparison plots from DebateBench outputs.

Usage example:
python3 scripts/extra_plots.py \
  --debates results/results_sample5/debates_sample5-11-30-2025_final.jsonl \
  --topics configs/topics.json \
  --viz-dir results/viz_sample5-11-30-2025_final \
  --out-dir results/plots_sample5-11-30-2025_final_extra
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from debatebench.plot_style import apply_dark_theme, style_axes

def load_debates(path: Path) -> List[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def compute_head_to_head(debates: Iterable[dict]) -> pd.DataFrame:
    wins: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    ties: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    models = set()

    for d in debates:
        pro = d["transcript"]["pro_model_id"]
        con = d["transcript"]["con_model_id"]
        winner = d["aggregate"]["winner"]
        models.update((pro, con))
        if winner == "pro":
            wins[pro][con] += 1
        elif winner == "con":
            wins[con][pro] += 1
        else:
            ties[pro][con] += 1
            ties[con][pro] += 1

    rows: List[Tuple[str, str, int, int, int, float]] = []
    for a in models:
        for b in models:
            if a == b:
                continue
            w_ab = wins[a].get(b, 0)
            w_ba = wins[b].get(a, 0)
            t = ties[a].get(b, 0)
            total = w_ab + w_ba + t
            winrate = (w_ab + 0.5 * t) / total if total else np.nan
            rows.append((a, b, w_ab, w_ba, t, winrate))

    return pd.DataFrame(
        rows, columns=["model_a", "model_b", "wins_a", "wins_b", "ties", "winrate_a"]
    )


def compute_side_bias(debates: Iterable[dict]) -> pd.DataFrame:
    stats = defaultdict(lambda: {"pro_w": 0, "pro_l": 0, "pro_t": 0, "con_w": 0, "con_l": 0, "con_t": 0})
    for d in debates:
        pro = d["transcript"]["pro_model_id"]
        con = d["transcript"]["con_model_id"]
        winner = d["aggregate"]["winner"]
        if winner == "pro":
            stats[pro]["pro_w"] += 1
            stats[con]["con_l"] += 1
        elif winner == "con":
            stats[con]["con_w"] += 1
            stats[pro]["pro_l"] += 1
        else:
            stats[pro]["pro_t"] += 1
            stats[con]["con_t"] += 1

    rows = []
    for model, s in stats.items():
        pro_games = s["pro_w"] + s["pro_l"] + s["pro_t"]
        con_games = s["con_w"] + s["con_l"] + s["con_t"]
        pro_rate = (s["pro_w"] + 0.5 * s["pro_t"]) / pro_games if pro_games else np.nan
        con_rate = (s["con_w"] + 0.5 * s["con_t"]) / con_games if con_games else np.nan
        gap = pro_rate - con_rate if not np.isnan(pro_rate) and not np.isnan(con_rate) else np.nan
        rows.append((model, pro_rate, con_rate, gap, pro_games, con_games))

    return pd.DataFrame(rows, columns=["model", "pro_rate", "con_rate", "gap", "pro_games", "con_games"])


def compute_category_winrate(debates: Iterable[dict], topics_path: Path) -> pd.DataFrame:
    with topics_path.open() as f:
        topic_cats = {t["id"]: t["category"] for t in json.load(f)}

    stats: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"w": 0, "l": 0, "t": 0}))
    for d in debates:
        cat = topic_cats.get(d["transcript"]["topic"]["id"], "unknown")
        pro = d["transcript"]["pro_model_id"]
        con = d["transcript"]["con_model_id"]
        winner = d["aggregate"]["winner"]
        if winner == "pro":
            stats[pro][cat]["w"] += 1
            stats[con][cat]["l"] += 1
        elif winner == "con":
            stats[con][cat]["w"] += 1
            stats[pro][cat]["l"] += 1
        else:
            stats[pro][cat]["t"] += 1
            stats[con][cat]["t"] += 1

    rows = []
    for model, cats in stats.items():
        for cat, s in cats.items():
            games = s["w"] + s["l"] + s["t"]
            winrate = (s["w"] + 0.5 * s["t"]) / games if games else np.nan
            rows.append((model, cat, winrate, games, s["w"], s["l"], s["t"]))

    return pd.DataFrame(
        rows, columns=["model", "category", "winrate", "games", "wins", "losses", "ties"]
    )


def compute_volatility(debates: Iterable[dict]) -> pd.DataFrame:
    buckets: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for d in debates:
        pro = d["transcript"]["pro_model_id"]
        con = d["transcript"]["con_model_id"]
        agg = d["aggregate"]
        for dim, score in agg["mean_pro"].items():
            buckets[(pro, dim)].append(score)
        for dim, score in agg["mean_con"].items():
            buckets[(con, dim)].append(score)

    rows = []
    for (model, dim), values in buckets.items():
        arr = np.array(values, dtype=float)
        mean = float(arr.mean()) if len(arr) else np.nan
        std = float(arr.std()) if len(arr) else np.nan
        rows.append((model, dim, mean, std, len(arr)))

    return pd.DataFrame(rows, columns=["model", "dimension", "mean", "std", "n"])


def plot_heatmap(
    df: pd.DataFrame,
    out_path: Path,
    cmap,
    title: str,
    fmt: str = ".2f",
    vmin=None,
    vmax=None,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.heatmap(
        df,
        annot=True,
        fmt=fmt,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        ax=ax,
        annot_kws={"color": "#e9eef7", "fontsize": 9},
    )
    ax.set_title(title)
    style_axes(ax)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extra comparison plots for DebateBench results")
    parser.add_argument("--debates", type=Path, required=True, help="Path to debates JSONL file")
    parser.add_argument("--topics", type=Path, required=True, help="Path to topics.json")
    parser.add_argument("--viz-dir", type=Path, required=True, help="Path to existing viz CSV directory")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory to write plots/CSVs")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    palettes = apply_dark_theme()

    debates = load_debates(args.debates)

    # Head-to-head matrix
    h2h = compute_head_to_head(debates)
    h2h.to_csv(args.out_dir / "head_to_head_table.csv", index=False)
    matrix = h2h.pivot(index="model_a", columns="model_b", values="winrate_a")
    plot_heatmap(
        matrix,
        args.out_dir / "head_to_head_winrate.png",
        cmap=palettes["seq_cmap"],
        title="Head-to-Head Winrate (row beats column)",
        vmin=0,
        vmax=1,
    )

    # Side bias
    side = compute_side_bias(debates).sort_values("gap", ascending=False)
    side.to_csv(args.out_dir / "side_bias.csv", index=False)
    plt.figure(figsize=(8, 5))
    sns.barplot(
        data=side,
        x="gap",
        y="model",
        hue="gap",
        palette=palettes["seq"],
        legend=False,
        order=side["model"],
    )
    plt.axvline(0, color="black", linewidth=1)
    plt.title("Pro vs Con Winrate Gap (positive = better as PRO)")
    plt.xlabel("Pro winrate - Con winrate")
    style_axes(plt.gca())
    plt.tight_layout()
    plt.savefig(args.out_dir / "side_bias_gap.png", bbox_inches="tight")
    plt.close()

    # Topic category specialization
    cat = compute_category_winrate(debates, args.topics)
    cat.to_csv(args.out_dir / "category_winrate.csv", index=False)
    pivot = cat.pivot(index="model", columns="category", values="winrate")
    plot_heatmap(
        pivot,
        args.out_dir / "category_winrate_heatmap.png",
        cmap=palettes["seq_cmap"],
        title="Winrate by Topic Category",
        vmin=0,
        vmax=1,
    )

    # Judge effects
    agree_path = args.viz_dir / "judge_agreement.csv"
    align_path = args.viz_dir / "judge_majority_alignment.csv"
    agree_df = pd.read_csv(agree_path)
    align_df = pd.read_csv(align_path)

    judges = sorted(set(agree_df["judge_a"]).union(set(agree_df["judge_b"])))
    mat = pd.DataFrame(np.nan, index=judges, columns=judges)
    for _, row in agree_df.iterrows():
        a, b, rate = row["judge_a"], row["judge_b"], row["agreement_rate"]
        mat.loc[a, b] = rate
        mat.loc[b, a] = rate
    np.fill_diagonal(mat.values, 1.0)
    plot_heatmap(
        mat,
        args.out_dir / "judge_agreement_heatmap.png",
        cmap=palettes["seq_cmap"],
        title="Judge Winner Agreement",
        fmt=".2f",
        vmin=0,
        vmax=1,
    )

    align_df = align_df.sort_values("alignment_rate", ascending=False)
    plt.figure(figsize=(8, 5))
    sns.barplot(
        data=align_df,
        x="alignment_rate",
        y="judge_id",
        hue="alignment_rate",
        palette=palettes["seq"],
        legend=False,
    )
    plt.title("Judge Alignment with Panel Majority")
    plt.xlabel("Alignment rate")
    style_axes(plt.gca())
    plt.tight_layout()
    plt.savefig(args.out_dir / "judge_alignment.png", bbox_inches="tight")
    plt.close()

    # Style trade-offs & volatility
    gap_df = pd.read_csv(args.viz_dir / "dimension_score_gaps.csv")
    pivot_gap = gap_df.pivot(index="debate_id", columns="dimension", values="gap")
    corr = pivot_gap.corr()
    plot_heatmap(
        corr,
        args.out_dir / "dimension_gap_corr.png",
        cmap=palettes["div_cmap"],
        title="Dimension Gap Correlations",
        fmt=".2f",
    )

    scatter_df = pivot_gap.reset_index()
    plt.figure(figsize=(6, 5))
    sns.scatterplot(data=scatter_df, x="persuasiveness", y="factuality", alpha=0.5, color=palettes["seq"][0])
    plt.axhline(0, color="black", linewidth=1)
    plt.axvline(0, color="black", linewidth=1)
    plt.title("Debate-Level Gaps: Persuasiveness vs Factuality")
    style_axes(plt.gca())
    plt.tight_layout()
    plt.savefig(args.out_dir / "persuasiveness_vs_factuality.png", bbox_inches="tight")
    plt.close()

    vol_df = compute_volatility(debates)
    vol_df.to_csv(args.out_dir / "model_dimension_volatility.csv", index=False)
    vol_pivot = vol_df.pivot(index="model", columns="dimension", values="std")
    plot_heatmap(
        vol_pivot,
        args.out_dir / "model_dimension_volatility.png",
        cmap=palettes["seq_cmap"],
        title="Score Volatility (Std Dev)",
        fmt=".2f",
    )

    print(f"Wrote plots to {args.out_dir}")


if __name__ == "__main__":
    main()
