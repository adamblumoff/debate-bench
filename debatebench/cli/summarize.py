"""`debatebench summarize` command."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import typer

from ..storage import load_debate_records
from .common import console


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
    - judge_side_preference.csv (per-judge pro/con/tie rates)
    - model_winrate_by_side.csv (wins/losses/ties when model is PRO vs CON)
    - judge_majority_alignment.csv (% of debates where judge matches panel)
    - dimension_score_gaps.csv (mean_pro - mean_con per dimension per debate)
    - turn_timings.csv (mean turn duration per model side)
    - token_usage.csv (mean prompt/completion tokens per model side)
    - cost_usage.csv (mean observed USD cost per model side; falls back to tokens if missing)
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
    cost_usage = defaultdict(lambda: {"pro_cost": [], "con_cost": []})
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
            if t.cost is not None:
                key = f"{side}_cost"
                cost_usage[model_id][key].append(t.cost)
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

    # Cost usage per model side (observed from OpenRouter usage, if present)
    with (out_dir / "cost_usage.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model_id", "side", "mean_cost_usd", "samples"])
        for model_id, buckets in sorted(cost_usage.items()):
            for side in ("pro", "con"):
                key = f"{side}_cost"
                vals = buckets[key]
                cnt = len(vals)
                mean_cost = sum(vals) / cnt if cnt else 0.0
                writer.writerow([model_id, side, f"{mean_cost:.6f}", cnt])

    # Judge agreement matrix (winner label agreement)
    pair_agree = defaultdict(int)
    pair_total = defaultdict(int)
    judge_match_majority = defaultdict(int)
    judge_total = defaultdict(int)
    judge_winner_counts = defaultdict(lambda: {"pro": 0, "con": 0, "tie": 0})
    for d in debates:
        winners = {j.judge_id: j.winner for j in d.judges}
        ids = list(winners.keys())
        majority = d.aggregate.winner
        for j_id, win in winners.items():
            judge_total[j_id] += 1
            if win == majority:
                judge_match_majority[j_id] += 1
            if win in ("pro", "con", "tie"):
                judge_winner_counts[j_id][win] += 1
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

    # Judge side preference (per-judge pro/con/tie rates)
    with (out_dir / "judge_side_preference.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "judge_id",
                "pro",
                "con",
                "tie",
                "total",
                "pro_rate",
                "con_rate",
                "tie_rate",
            ]
        )
        for j_id, counts in sorted(judge_winner_counts.items()):
            total = sum(counts.values())
            pro = counts["pro"]
            con = counts["con"]
            tie = counts["tie"]
            pro_rate = pro / total if total else 0.0
            con_rate = con / total if total else 0.0
            tie_rate = tie / total if total else 0.0
            writer.writerow(
                [
                    j_id,
                    pro,
                    con,
                    tie,
                    total,
                    f"{pro_rate:.4f}",
                    f"{con_rate:.4f}",
                    f"{tie_rate:.4f}",
                ]
            )

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


__all__ = ["summarize"]
