"""
CLI entrypoints for DebateBench.
"""
from __future__ import annotations

import itertools
import hashlib
import json
import shutil
from typing import Dict, Tuple
import requests
import random
import time
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError

from . import config as cfg
from .debate import run_debate, EmptyResponseError
from .judge import run_judge_panel
from .models import build_debater_adapter, build_judge_adapter, sample_judges
from .openrouter import fetch_recent_openrouter_models, probe_model
from .rating import recompute_ratings
from .schema import DebateRecord, DebaterModelConfig, JudgeModelConfig
from .storage import append_debate_record, load_debate_records, read_ratings, write_ratings
from .settings import load_settings
from .plot_style import apply_dark_theme, style_axes
from collections import defaultdict
import csv
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

app = typer.Typer(help="DebateBench CLI")
console = Console()


def _path_option(default: str, help_text: str):
    return typer.Option(default, help=help_text, dir_okay=True, file_okay=True, readable=True, writable=True)


class SelectionCancelled(Exception):
    """Raised when the user cancels the selection wizard."""


def _interactive_select_models(catalog, console: Console, title: str = "OpenRouter Models (alphabetical)"):
    """
    Curses-based selector: arrow keys to move, Enter/Space to toggle, c to continue, q to cancel.
    Falls back to simple enable prompt if curses is unavailable.
    """
    try:
        import curses
    except Exception:
        return _fallback_select_models(catalog, console)

    def menu(stdscr):
        curses.curs_set(0)
        selected = [False] * len(catalog)
        idx = 0

        def draw():
            stdscr.clear()
            header = f"{title} (Enter/Space toggle ON/OFF, ↑/↓ move, c=continue, q=cancel; default is OFF)"
            stdscr.addstr(0, 0, header, curses.A_BOLD)
            max_rows = curses.LINES - 2
            start = max(0, idx - max_rows + 1)
            visible = catalog[start : start + max_rows]
            for offset, entry in enumerate(visible):
                real_idx = start + offset
                cursor = ">" if real_idx == idx else " "
                mark = "[x]" if selected[real_idx] else "[ ]"
                line = f"{cursor} {mark} {entry['id']} ({entry['created'].strftime('%Y-%m-%d')})"
                stdscr.addstr(offset + 1, 0, line[: curses.COLS - 1])
            stdscr.refresh()

        draw()
        while True:
            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(catalog)
            elif ch in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(catalog)
            elif ch in (10, 13, ord(" "), ord("\n")):  # Enter or space toggles
                selected[idx] = not selected[idx]
            elif ch in (ord("c"), ord("C")):  # continue
                return [c for i, c in enumerate(catalog) if selected[i]]
            elif ch in (ord("q"), ord("Q")):
                return []
            draw()

    try:
        return curses.wrapper(menu)
    except Exception:
        return _fallback_select_models(catalog, console)


def _fallback_select_models(catalog, console: Console, title: str = "OpenRouter Models (alphabetical)"):
    """
    Simpler prompt fallback: show table, accept comma-separated indexes to enable.
    """
    table = Table(title=title)
    table.add_column("#", justify="right")
    table.add_column("Model ID")
    table.add_column("Created (UTC)")
    for idx, entry in enumerate(catalog, start=1):
        table.add_row(str(idx), entry["id"], entry["created"].strftime("%Y-%m-%d"))
    console.print(table)

    prompt_text = "Enter comma-separated indexes to enable (blank enables none): "
    disable_raw = typer.prompt(prompt_text, default="")
    enabled: set[int] = set()
    if disable_raw.strip():
        parts = [p.strip() for p in disable_raw.split(",")]
        for p in parts:
            if not p:
                continue
            try:
                val = int(p)
            except ValueError:
                raise typer.BadParameter(f"Invalid index: {p}")
            if val < 1 or val > len(catalog):
                raise typer.BadParameter(f"Index out of range: {val}")
            enabled.add(val)

    return [e for idx, e in enumerate(catalog, start=1) if idx in enabled]


def _interactive_select_topics(topics, console: Console):
    """
    Topic selector shown before models. Defaults to OFF; user toggles ON.
    """
    try:
        import curses
    except Exception:
        return _fallback_select_topics(topics, console)

    topics_sorted = sorted(topics, key=lambda t: (t.category or "", t.motion))

    def menu(stdscr):
        curses.curs_set(0)
        selected = [False] * len(topics_sorted)
        idx = 0

        def draw():
            stdscr.clear()
            stdscr.addstr(
                0,
                0,
                "Topics (Enter/Space toggle ON/OFF, ↑/↓ move, c=continue, q=cancel; default is OFF)",
                curses.A_BOLD,
            )
            max_rows = curses.LINES - 2
            start = max(0, idx - max_rows + 1)
            visible = topics_sorted[start : start + max_rows]
            for offset, entry in enumerate(visible):
                real_idx = start + offset
                cursor = ">" if real_idx == idx else " "
                mark = "[x]" if selected[real_idx] else "[ ]"
                motion = entry.motion if len(entry.motion) < curses.COLS - 20 else entry.motion[: curses.COLS - 23] + "..."
                cat = entry.category or "-"
                line = f"{cursor} {mark} {cat}: {motion}"
                stdscr.addstr(offset + 1, 0, line[: curses.COLS - 1])
            stdscr.refresh()

        draw()
        while True:
            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(topics)
            elif ch in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(topics)
            elif ch in (10, 13, ord(" "), ord("\n")):  # Enter or space toggles
                selected[idx] = not selected[idx]
            elif ch in (ord("c"), ord("C")):  # continue
                return [t for i, t in enumerate(topics_sorted) if selected[i]]
            elif ch in (ord("q"), ord("Q")):
                return []
            draw()

    try:
        return curses.wrapper(menu)
    except Exception:
        return _fallback_select_topics(topics, console)


def _fallback_select_topics(topics, console: Console):
    table = Table(title="Topics")
    table.add_column("#", justify="right")
    table.add_column("Category")
    table.add_column("Motion")
    table.add_column("Category")
    topics_sorted = sorted(topics, key=lambda t: (t.category or "", t.motion))
    for idx, t in enumerate(topics_sorted, start=1):
        table.add_row(str(idx), t.category or "-", t.motion, t.category or "-")
    console.print(table)
    prompt_text = "Enter comma-separated indexes to ENABLE (blank enables none): "
    raw = typer.prompt(prompt_text, default="")
    enabled: set[int] = set()
    if raw.strip():
        parts = [p.strip() for p in raw.split(",")]
        for p in parts:
            if not p:
                continue
            try:
                val = int(p)
            except ValueError:
                raise typer.BadParameter(f"Invalid index: {p}")
            if val < 1 or val > len(topics_sorted):
                raise typer.BadParameter(f"Index out of range: {val}")
            enabled.add(val)
    return [t for idx, t in enumerate(topics_sorted, start=1) if idx in enabled]


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds*1000:.0f} ms"
    delta = timedelta(seconds=int(seconds))
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if delta.days:
        parts.append(f"{delta.days}d")
    if hours or delta.days:
        parts.append(f"{hours}h")
    if minutes or hours or delta.days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _historical_debate_durations(results_dir: Path, max_files: int = 5, max_records: int = 500) -> Tuple[float | None, int]:
    """
    Return (median_total_seconds, num_records) from recent debate files.
    Total seconds = sum(turn.duration_ms) + sum(judge.latency_ms) for each debate.
    """
    totals = []
    files = sorted(results_dir.glob("debates_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for idx, path in enumerate(files):
        try:
            records = load_debate_records(path)
        except Exception:
            continue
        for rec in records:
            turn_ms = sum(t.duration_ms or 0 for t in rec.transcript.turns)
            judge_ms = sum(j.latency_ms or 0 for j in rec.judges)
            total_ms = turn_ms + judge_ms
            if total_ms > 0:
                totals.append(total_ms / 1000.0)
            if len(totals) >= max_records:
                break
        if len(totals) >= max_records:
            break
        if idx + 1 >= max_files:
            break
    if not totals:
        return None, 0
    return statistics.median(totals), len(totals)


def selection_wizard(
    topics,
    model_catalog,
    judge_catalog,
    enable_topics: bool,
    enable_models: bool,
    enable_judges: bool,
    popular_ids: List[str] | None = None,
):
    """
    Unified curses wizard for topic/model/judge selection.
    Returns (selected_topics, selected_models, selected_judges) or None if cancelled.
    """
    try:
        import curses
    except Exception:
        return None

    steps = []
    if enable_topics and topics:
        topics_sorted = sorted(topics, key=lambda t: (t.category or "", t.motion))
        steps.append(
            {
                "name": "Topics",
                "items": topics_sorted,
                "selected": [False] * len(topics_sorted),
                "type": "topic",
            }
        )
    if enable_models and model_catalog:
        steps.append(
            {
                "name": "Debaters",
                "items": model_catalog,
                "selected": [False] * len(model_catalog),
                "type": "model",
            }
        )
    if enable_judges and judge_catalog:
        steps.append(
            {
                "name": "Judges",
                "items": judge_catalog,
                "selected": [False] * len(judge_catalog),
                "type": "judge",
            }
        )

    if not steps:
        return None

    def render_line(stdscr, row, text, highlight=False):
        maxw = curses.COLS - 1
        txt = text[: maxw]
        if highlight:
            stdscr.addstr(row, 0, txt, curses.A_REVERSE)
        else:
            stdscr.addstr(row, 0, txt)

    def menu(stdscr):
        curses.curs_set(0)
        step_idx = 0
        cursor_idx = 0

        def clamp_cursor():
            nonlocal cursor_idx
            curr_items = steps[step_idx]["items"]
            if not curr_items:
                cursor_idx = 0
            else:
                cursor_idx = max(0, min(cursor_idx, len(curr_items) - 1))

        def draw():
            stdscr.clear()
            step = steps[step_idx]
            total_steps = len(steps)
            header = (
                f"Step {step_idx+1}/{total_steps} - {step['name']} "
                "(Space/Enter toggle, ↑/↓ move, n=next, b=back, q=cancel)"
            )
            render_line(stdscr, 0, header, highlight=True)
            items = step["items"]
            selected = step["selected"]
            max_rows = curses.LINES - 2
            start = max(0, cursor_idx - max_rows + 1)
            visible = items[start : start + max_rows]
            for offset, entry in enumerate(visible):
                real_idx = start + offset
                cursor = ">" if real_idx == cursor_idx else " "
                mark = "[x]" if selected[real_idx] else "[ ]"
                if step["type"] == "topic":
                    cat = entry.category or "-"
                    motion = entry.motion
                    desc = f"{cat}: {motion}"
                else:
                    created = entry.get("created")
                    cstr = created.strftime("%Y-%m-%d") if created else ""
                    desc = f"{entry.get('id')} ({cstr})"
                line = f"{cursor} {mark} {desc}"
                render_line(stdscr, offset + 1, line)
            stdscr.refresh()

        draw()
        while True:
            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                cursor_idx = max(0, cursor_idx - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                cursor_idx = min(len(steps[step_idx]["items"]) - 1, cursor_idx + 1)
            elif ch in (10, 13, ord(" "), ord("\n")):
                if steps[step_idx]["items"]:
                    steps[step_idx]["selected"][cursor_idx] = not steps[step_idx]["selected"][cursor_idx]
            elif ch in (ord("n"), ord("N")):
                if step_idx < len(steps) - 1:
                    step_idx += 1
                    clamp_cursor()
                else:
                    break
            elif ch in (ord("b"), ord("B")):
                if step_idx > 0:
                    step_idx -= 1
                    clamp_cursor()
            elif ch in (ord("q"), ord("Q")):
                raise SelectionCancelled()
            draw()

        # Gather selections
        sel_topics = []
        sel_models = []
        sel_judges = []
        for st in steps:
            if st["type"] == "topic":
                sel_topics = [t for i, t in enumerate(st["items"]) if st["selected"][i]]
            elif st["type"] == "model":
                sel_models = [m for i, m in enumerate(st["items"]) if st["selected"][i]]
            elif st["type"] == "judge":
                sel_judges = [m for i, m in enumerate(st["items"]) if st["selected"][i]]
        return sel_topics, sel_models, sel_judges

    return curses.wrapper(menu)


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
        12345, help="Random seed for reproducibility (default 12345)."
    ),
    swap_sides: bool = typer.Option(
        False, help="Randomly swap Pro/Con assignment per debate (ignored if --balanced-sides)."
    ),
    balanced_sides: bool = typer.Option(
        True, help="Ensure each model pair plays both sides (permutations). Disable for combinations."
    ),
    balanced_judges: bool = typer.Option(
        True,
        "--balanced-judges/--random-judges",
        help="Balance judge usage across the run (default). Disable to sample judges uniformly at random.",
    ),
    openrouter_select: bool = typer.Option(
        True,
        "--openrouter-select/--no-openrouter-select",
        help="Interactively select OpenRouter models (default on; overrides models.yaml debaters).",
    ),
    openrouter_months: int = typer.Option(
        4, help="Lookback window in months for OpenRouter model selection."
    ),
    openrouter_temperature: float = typer.Option(
        0.7, help="Default temperature for OpenRouter debater adapters."
    ),
    openrouter_max_tokens: int = typer.Option(
        3200, help="Max tokens per debater completion when using OpenRouter models."
    ),
    openrouter_probe: bool = typer.Option(
        True, help="Probe each selected OpenRouter model before running; drop any that fail."
    ),
    judges_from_selection: bool = typer.Option(
        False,
        help="Use the selected debater models as the judge pool and sample a panel per debate.",
    ),
    openrouter_judge_months: Optional[int] = typer.Option(
        None,
        help="Lookback window in months for OpenRouter judge selection (defaults to openrouter-months).",
    ),
    openrouter_judge_max_tokens: int = typer.Option(
        256, help="Max tokens per judge completion when using OpenRouter models."
    ),
    topic_select: bool = typer.Option(
        True,
        "--topic-select/--no-topic-select",
        help="Interactively select topics before model selection (default on).",
    ),
    tui_wizard: bool = typer.Option(
        True,
        "--tui-wizard/--no-tui-wizard",
        help="Use a single curses wizard for topic/model/judge selection when available (default on).",
    ),
    apply_stage_token_limits: bool = typer.Option(
        True,
        help="Apply default per-stage token limits (opening=900, rebuttal=600, closing=400) to rounds before running.",
    ),
    skip_on_empty: bool = typer.Option(
        False,
        help="If a model returns empty content after retries, skip that model for the rest of the run instead of aborting all debates.",
    ),
    quick_test: bool = typer.Option(
        False,
        help="Run a fixed sanity test: 1 random topic, Google Gemini 3 Pro Preview vs OpenAI GPT-5.1, judges Kimi K2 Thinking + Claude Opus 4.5 + DeepSeek V3.2.",
    ),
    judges_test: bool = typer.Option(
        False,
        help="Run a fixed judge-focused test: 1 random topic, debaters Claude Haiku 4.5 (pro) vs Gemini 2.5 Flash Lite Preview, judges Gemini 3 Pro Preview + OpenAI GPT-5.1.",
    ),
    high_tokens: bool = typer.Option(
        True,
        help="Generous token budgets for quality: opening=3200, rebuttal=3200, closing=3200; bump debater max_tokens to at least 3200 and judges to 512 (x5 safety).",
    ),
    resume: bool = typer.Option(
        False,
        help="Resume a previous run: skip debates already present in the debates file for this run_tag.",
    ),
    retry_failed: bool = typer.Option(
        True,
        "--retry-failed/--no-retry-failed",
        help="After completing the planned schedule, retry debates that failed (once).",
    ),
    dry_run: bool = typer.Option(
        False,
        help="Plan the run (models/topics/pairs) and exit without executing debates.",
    ),
    postrate: bool = typer.Option(
        True,
        "--postrate/--no-postrate",
        help="After debates finish, recompute ratings and show leaderboard.",
    ),
    estimate_time: bool = typer.Option(
        True,
        help="Estimate total wall-clock time using recent runs (median) and planned debate count.",
    ),
):
    """
    Run a batch of debates and append results.
    """
    main_cfg, topics, debater_models, judge_models = cfg.load_all_configs(
        config_path, topics_path, models_path, judges_path
    )

    # Apply per-stage token limits if enabled
    if apply_stage_token_limits:
        if high_tokens:
            stage_limits = {"opening": 3200, "rebuttal": 3200, "closing": 3200}
        else:
            stage_limits = {"opening": 900, "rebuttal": 600, "closing": 400}
        new_rounds = []
        for r in main_cfg.rounds:
            lim = stage_limits.get(r.stage, r.token_limit)
            new_rounds.append(r.copy(update={"token_limit": lim}))
        main_cfg.rounds = new_rounds

    # derive run tag and output paths
    if not run_tag:
        run_tag = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
    debates_path = debates_path.parent / f"debates_{run_tag}.jsonl"
    run_dir = Path("results") / f"run_{run_tag}"
    viz_dir = Path("results") / f"viz_{run_tag}"
    plots_dir = Path("results") / f"plots_{run_tag}"
    ratings_path = Path("results") / f"ratings_{run_tag}.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = run_dir / "config_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    # Preserve input config files and CLI args for reproducibility
    for src in (config_path, topics_path, models_path, judges_path):
        try:
            shutil.copy(src, snapshot_dir / src.name)
        except FileNotFoundError:
            pass
    cli_args = {
        "config_path": str(config_path),
        "topics_path": str(topics_path),
        "models_path": str(models_path),
        "judges_path": str(judges_path),
        "debates_path_arg": str(debates_path),
        "run_tag": run_tag,
        "sample_topics": sample_topics,
        "debates_per_pair": debates_per_pair,
        "seed": seed,
        "swap_sides": swap_sides,
        "balanced_sides": balanced_sides,
        "balanced_judges": balanced_judges,
        "openrouter_select": openrouter_select,
        "openrouter_months": openrouter_months,
        "openrouter_temperature": openrouter_temperature,
        "openrouter_max_tokens": openrouter_max_tokens,
        "openrouter_probe": openrouter_probe,
        "judges_from_selection": judges_from_selection,
        "openrouter_judge_months": openrouter_judge_months,
        "openrouter_judge_max_tokens": openrouter_judge_max_tokens,
        "topic_select": topic_select,
        "tui_wizard": tui_wizard,
        "apply_stage_token_limits": apply_stage_token_limits,
        "skip_on_empty": skip_on_empty,
        "quick_test": quick_test,
        "judges_test": judges_test,
        "high_tokens": high_tokens,
        "resume": resume,
        "retry_failed": retry_failed,
        "dry_run": dry_run,
        "postrate": postrate,
    }
    with (snapshot_dir / "cli_args.json").open("w", encoding="utf-8") as f:
        json.dump(cli_args, f, indent=2)

    if not topics:
        raise typer.BadParameter("Topics list is empty.")

    rng = random.Random(seed)
    settings = load_settings()

    topics_selected = topics
    judge_output_max_tokens = int(openrouter_judge_max_tokens * 5)

    def derive_debate_seed(tag: str, topic_id: str, pro_id: str, con_id: str, rep: int) -> int:
        """
        Deterministically derive a per-debate seed so resumes reproduce the same
        side swaps and judge panels.
        """
        key = f"{tag}|{topic_id}|{pro_id}|{con_id}|{rep}".encode("utf-8")
        digest = hashlib.blake2s(key, digest_size=8).digest()
        # keep in 32-bit range for Random
        return int.from_bytes(digest, "big") & 0x7FFFFFFF

    def select_judges(
        pool, expected: int, seed_val: int, usage_counts: dict[str, int]
    ):
        if len(pool) < expected:
            raise typer.BadParameter(
                f"Need at least {expected} judges after exclusions; found {len(pool)}."
            )
        rng = random.Random(seed_val)
        if balanced_judges:
            ordered = sorted(
                pool,
                key=lambda j: (usage_counts.get(j.id, 0), rng.random(), j.id),
            )
            return ordered[:expected]
        return rng.sample(pool, expected)

    if quick_test and judges_test:
        raise typer.BadParameter("Choose only one of --quick-test or --judges-test.")

    if quick_test:
        rng = random.Random(seed)
        topics_selected = [rng.choice(topics)]
        debater_models = [
            DebaterModelConfig(
                id="google-gemini-3-pro-preview",
                provider="openrouter",
                model="google/gemini-3-pro-preview",
                token_limit=openrouter_max_tokens,
                endpoint=None,
                parameters={"temperature": 0.35 if high_tokens else openrouter_temperature},
            ),
            DebaterModelConfig(
                id="openai-gpt-5.1",
                provider="openrouter",
                model="openai/gpt-5.1",
                token_limit=openrouter_max_tokens,
                endpoint=None,
                parameters={"temperature": 0.35 if high_tokens else openrouter_temperature},
            ),
        ]
        judge_models = [
            JudgeModelConfig(
                id="moonshotai-kimi-k2-thinking",
                provider="openrouter",
                model="moonshotai/kimi-k2-thinking",
                token_limit=judge_output_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": openrouter_temperature},
            ),
            JudgeModelConfig(
                id="anthropic-claude-opus-4.5",
                provider="openrouter",
                model="anthropic/claude-opus-4.5",
                token_limit=judge_output_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": openrouter_temperature},
            ),
            JudgeModelConfig(
                id="deepseek-deepseek-v3.2-exp",
                provider="openrouter",
                model="deepseek/deepseek-v3.2-exp",
                token_limit=judge_output_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": openrouter_temperature},
            ),
        ]
        main_cfg.num_judges = 3
        console.print("[cyan]Quick test mode: 1 random topic, fixed debaters and judges.[/cyan]")
    elif judges_test:
        rng = random.Random(seed)
        topics_selected = [rng.choice(topics)]
        balanced_sides = False  # single orientation: pro=first model, con=second
        debates_per_pair = 1
        debater_models = [
            DebaterModelConfig(
                id="anthropic-claude-haiku-4.5",
                provider="openrouter",
                model="anthropic/claude-haiku-4.5",
                token_limit=openrouter_max_tokens,
                endpoint=None,
                parameters={"temperature": 0.35 if high_tokens else openrouter_temperature},
            ),
            DebaterModelConfig(
                id="google-gemini-2.5-flash-lite-preview-09-2025",
                provider="openrouter",
                model="google/gemini-2.5-flash-lite-preview-09-2025",
                token_limit=openrouter_max_tokens,
                endpoint=None,
                parameters={"temperature": 0.35 if high_tokens else openrouter_temperature},
            ),
        ]
        judge_models = [
            JudgeModelConfig(
                id="google-gemini-3-pro-preview",
                provider="openrouter",
                model="google/gemini-3-pro-preview",
                token_limit=judge_output_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": 0.0},
            ),
            JudgeModelConfig(
                id="openai-gpt-5.1",
                provider="openrouter",
                model="openai/gpt-5.1",
                token_limit=judge_output_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": 0.0},
            ),
        ]
        main_cfg.num_judges = 2
        console.print("[cyan]Judges test mode: 1 random topic, Claude Haiku 4.5 vs Gemini 2.5 Flash Lite; judges Gemini 3 Pro + OpenAI GPT-5.1.[/cyan]")
    else:
        # Pre-fetch catalogs for wizard and/or standalone pickers
        debater_catalog = None
        if openrouter_select:
            if not settings.openrouter_api_key:
                raise typer.BadParameter("OPENROUTER_API_KEY is required for interactive OpenRouter selection.")
            console.print(
                f"[cyan]Fetching OpenRouter models from the last {openrouter_months} month(s)...[/cyan]"
            )
            debater_catalog = fetch_recent_openrouter_models(
                months=openrouter_months,
                api_key=settings.openrouter_api_key,
                site_url=settings.openrouter_site_url,
                site_name=settings.openrouter_site_name,
            )
            if not debater_catalog:
                raise typer.BadParameter(f"No text-based OpenRouter models found in the last {openrouter_months} month(s).")

        judge_catalog = None
        months_j = openrouter_judge_months or openrouter_months
        if not judges_from_selection:
            console.print(
                f"[cyan]Fetching OpenRouter judge candidates from the last {months_j} month(s)...[/cyan]"
            )
            judge_catalog = fetch_recent_openrouter_models(
                months=months_j,
                api_key=settings.openrouter_api_key,
                site_url=settings.openrouter_site_url,
                site_name=settings.openrouter_site_name,
            )
            if not judge_catalog:
                raise typer.BadParameter(f"No text-based OpenRouter models found in the last {months_j} month(s) for judges.")

        # Wizard (topics -> debaters -> judges) if enabled and curses is available
        used_wizard = False
        if tui_wizard:
            try:
                wizard_result = selection_wizard(
                    topics=topics if topic_select else [],
                    model_catalog=debater_catalog if openrouter_select else [],
                    judge_catalog=judge_catalog if (not judges_from_selection) else [],
                    enable_topics=topic_select,
                    enable_models=openrouter_select,
                    enable_judges=not judges_from_selection,
                )
            except SelectionCancelled:
                console.print("[yellow]Selection cancelled.[/yellow]")
                raise typer.Exit(code=1)
            if wizard_result is not None:
                used_wizard = True
                topics_selected, debater_entries, judge_entries = wizard_result
                if not topics_selected:
                    raise typer.BadParameter("All topics were disabled; nothing to run.")
                # build debater models
                debater_models = []
                for entry in debater_entries:
                    model_id = entry["id"]
                    debater_models.append(
                        DebaterModelConfig(
                            id=model_id.replace("/", "-"),
                            provider="openrouter",
                            model=model_id,
                            token_limit=openrouter_max_tokens,
                            endpoint=None,
                            parameters={"temperature": openrouter_temperature},
                        )
                    )
                if not debater_models:
                    raise typer.BadParameter("All models were disabled; nothing to run.")
                # build judges depending on path
                if judges_from_selection:
                    judge_models = debater_models
                else:
                    judge_models = []
                    for entry in judge_entries:
                        model_id = entry["id"]
                        judge_models.append(
                            JudgeModelConfig(
                                id=model_id.replace("/", "-"),
                                provider="openrouter",
                                model=model_id,
                                token_limit=openrouter_judge_max_tokens,
                                endpoint=None,
                                prompt_style=None,
                                parameters={"temperature": openrouter_temperature},
                            )
                        )
                    if not judge_models:
                        raise typer.BadParameter("All judge models were disabled; nothing to run.")
                # apply sample_topics after wizard selection
                if sample_topics is not None:
                    if sample_topics <= 0:
                        raise typer.BadParameter("sample_topics must be positive.")
                    topics_selected = rng.sample(topics_selected, k=min(sample_topics, len(topics_selected)))

        if not quick_test and not used_wizard:
            # Topic selection fallback
            topics_selected = topics
            if topic_select:
                topics_selected = _interactive_select_topics(topics, console)
                if not topics_selected:
                    raise typer.BadParameter("All topics were disabled; nothing to run.")
            if sample_topics is not None:
                if sample_topics <= 0:
                    raise typer.BadParameter("sample_topics must be positive.")
                topics_selected = rng.sample(topics_selected, k=min(sample_topics, len(topics_selected)))

            # Debater selection fallback
            if openrouter_select:
                selected_entries = _interactive_select_models(debater_catalog, console, title="Select Debater Models")
                if not selected_entries:
                    raise typer.BadParameter("All models were disabled; nothing to run.")

                debater_models = []
                for entry in selected_entries:
                    model_id = entry["id"]
                    debater_models.append(
                        DebaterModelConfig(
                            id=model_id.replace("/", "-"),
                            provider="openrouter",
                            model=model_id,
                            token_limit=openrouter_max_tokens,
                            endpoint=None,
                            parameters={"temperature": openrouter_temperature},
                        )
                    )
                console.print(
                    f"[green]Selected {len(debater_models)} debater models from OpenRouter (last {openrouter_months} month(s)).[/green]"
                )

            # Optional preflight probes (debater)
            if openrouter_probe and debater_models:
                console.print("[cyan]Probing selected models with 1-token requests...[/cyan]")
                usable = []
                dropped = []
                for m in debater_models:
                    err = probe_model(
                        model_id=m.model,
                        api_key=settings.openrouter_api_key,
                        site_url=settings.openrouter_site_url,
                        site_name=settings.openrouter_site_name,
                    )
                    if err is None:
                        usable.append(m)
                    else:
                        dropped.append((m, err))
                if dropped:
                    console.print("[yellow]Dropping models that failed probe:[/yellow]")
                    for m, err in dropped:
                        console.print(f"  [red]{m.model}[/red]: {err}")
                debater_models = usable
                if len(debater_models) < 2:
                    raise typer.BadParameter("Fewer than two usable models after probe; aborting.")

            # Configure judge pool fallback
            if judges_from_selection:
                judge_models = debater_models
                main_cfg.num_judges = min(max(main_cfg.num_judges, 2), len(judge_models))
                if len(judge_models) < 2:
                    raise typer.BadParameter("Need at least two judges after selection.")
            else:
                selected_judges = _interactive_select_models(judge_catalog, console, title="Select Judge Models")
                if not selected_judges:
                    raise typer.BadParameter("All judge models were disabled; nothing to run.")
                judge_models = []
                for entry in selected_judges:
                    model_id = entry["id"]
                    judge_models.append(
                        JudgeModelConfig(
                            id=model_id.replace("/", "-"),
                            provider="openrouter",
                            model=model_id,
                            token_limit=judge_output_max_tokens,
                            endpoint=None,
                            prompt_style=None,
                            parameters={"temperature": openrouter_temperature},
                        )
                    )
                if openrouter_probe and judge_models:
                    console.print("[cyan]Probing selected judge models with 1-token requests...[/cyan]")
                    usable_j = []
                    dropped_j = []
                    for j in judge_models:
                        err = probe_model(
                            model_id=j.model,
                            api_key=settings.openrouter_api_key,
                            site_url=settings.openrouter_site_url,
                            site_name=settings.openrouter_site_name,
                        )
                        if err is None:
                            usable_j.append(j)
                        else:
                            dropped_j.append((j, err))
                    if dropped_j:
                        console.print("[yellow]Dropping judges that failed probe:[/yellow]")
                        for j, err in dropped_j:
                            console.print(f"  [red]{j.model}[/red]: {err}")
                    judge_models = usable_j
        main_cfg.num_judges = min(max(main_cfg.num_judges, 2), len(judge_models))
        if len(judge_models) < main_cfg.num_judges:
            main_cfg.num_judges = len(judge_models)
        if main_cfg.num_judges < 2:
            raise typer.BadParameter("Need at least two judges in the final pool.")

    # Final clamp for both paths
    main_cfg.num_judges = min(max(main_cfg.num_judges, 2), len(judge_models))
    if len(judge_models) < main_cfg.num_judges:
        main_cfg.num_judges = len(judge_models)
    if main_cfg.num_judges < 2:
        raise typer.BadParameter("Need at least two judges in the final pool.")

    if len(debater_models) < 2:
        raise typer.BadParameter("Need at least two debater models after selection.")

    # If high_tokens, bump per-model token limits
    if high_tokens:
        for m in debater_models:
            if m.token_limit is None or m.token_limit < 3072:
                m.token_limit = 3072
        for j in judge_models:
            if j.token_limit is None or j.token_limit < 512:
                j.token_limit = 512

    selection_snapshot = {
        "main_config": main_cfg.dict(),
        "topics_selected": [t.dict() for t in topics_selected],
        "debater_models": [m.dict() for m in debater_models],
        "judge_models": [j.dict() for j in judge_models],
    }
    with (snapshot_dir / "effective_selection.json").open("w", encoding="utf-8") as f:
        json.dump(selection_snapshot, f, indent=2)

    def _fetch_pricing(models_needed: set[str]) -> Dict[str, Tuple[float, float]]:
        """
        Returns map model_id -> (prompt_price_per_token, completion_price_per_token) by hitting OpenRouter.
        Falls back to an empty mapping if the API fails; caller should handle missing entries.
        """
        pricing: Dict[str, Tuple[float, float]] = {}
        headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "Accept": "application/json"}
        if settings.openrouter_site_url:
            headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_site_name:
            headers["X-Title"] = settings.openrouter_site_name
        try:
            resp = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=30)
            resp.raise_for_status()
            payload = resp.json().get("data", [])
            for entry in payload:
                mid = entry.get("id")
                if mid in models_needed:
                    pr = entry.get("pricing") or {}
                    p = float(pr.get("prompt")) if pr.get("prompt") not in (None, "") else None
                    c = float(pr.get("completion")) if pr.get("completion") not in (None, "") else None
                    if p is not None and c is not None:
                        pricing[mid] = (p, c)
        except Exception:
            return {}
        return pricing

    def _estimate_cost(
        debaters, judges, rounds, num_topics, debates_per_pair, balanced, pairs
    ) -> Tuple[float, Dict[str, float], float, Dict[str, float]]:
        """
        Rough cost estimator using live OpenRouter pricing (USD per token) when available.
        Token model:
          - Debater: completion tokens = sum(token_limit for its stages); prompt tokens ~= sum(history before each turn)
            approximated as completion_total + (completion_total - first_turn_tokens)
          - Judge: prompt tokens = sum(token_limit for all turns); completion ~200 tokens JSON
        """
        models_needed = {m.model for m in debaters} | {j.model for j in judges}
        live = _fetch_pricing(models_needed)

        def side_token_budget():
            comp = sum(r.token_limit for r in rounds if r.speaker == "pro")  # same for con
            # approximate prompt as history accumulation: roughly comp + (comp - first_turn)
            first_turn = next(r.token_limit for r in rounds if r.speaker == "pro")
            prompt = comp + max(0, comp - first_turn)
            return prompt, comp

        prompt_side, comp_side = side_token_budget()
        per_model_cost: Dict[str, float] = {}
        total_debater_cost = 0.0
        debates_per_pair_total = debates_per_pair * num_topics
        for a, b in pairs:
            for model, tokens in ((a, (prompt_side, comp_side)), (b, (prompt_side, comp_side))):
                rates = live.get(model.model)
                if not rates:
                    continue
                p_rate, c_rate = rates
                prompt_tokens, comp_tokens = tokens
                cost = prompt_tokens * p_rate + comp_tokens * c_rate
                per_model_cost[model.id] = per_model_cost.get(model.id, 0.0) + cost * debates_per_pair_total
                total_debater_cost += cost * debates_per_pair_total

        transcript_tokens = sum(r.token_limit for r in rounds)
        judge_output_tokens = 200
        per_judge_cost: Dict[str, float] = {}
        total_judge_cost = 0.0
        judge_calls = len(pairs) * debates_per_pair_total
        for j in judges:
            rates = live.get(j.model)
            if not rates:
                continue
            p_rate, c_rate = rates
            cost = transcript_tokens * p_rate + judge_output_tokens * c_rate
            per_judge_cost[j.id] = cost * judge_calls
            total_judge_cost += cost * judge_calls

        return total_debater_cost, per_model_cost, total_judge_cost, per_judge_cost

    # Build adapters
    debater_adapters = {m.id: build_debater_adapter(m, settings) for m in debater_models}
    judge_adapters = {j.id: build_judge_adapter(j, settings) for j in judge_models}

    # Generate schedule of model pairs
    if balanced_sides:
        pairs = list(itertools.permutations(debater_models, 2))
    else:
        pairs = list(itertools.combinations(debater_models, 2))
    completed_counts = defaultdict(int)
    judge_usage = defaultdict(int)
    if resume and debates_path.exists():
        existing = load_debate_records(debates_path)
        for rec in existing:
            key = (rec.transcript.topic.id, rec.transcript.pro_model_id, rec.transcript.con_model_id)
            completed_counts[key] += 1
            for jres in rec.judges:
                judge_usage[jres.judge_id] += 1
        console.print(
            f"[cyan]Resume mode: found {len(existing)} completed debates in {debates_path}; will skip already-finished matchups.[/cyan]"
        )
    existing_completed = sum(completed_counts.values())
    def remaining_for(topic, a, b):
        done = completed_counts.get((topic.id, a.id, b.id), 0)
        return max(0, debates_per_pair - done)

    total_runs = sum(remaining_for(topic, a, b) for topic in topics_selected for (a, b) in pairs)
    console.print(f"Scheduled {total_runs} debates (remaining).")
    progress_path = run_dir / "progress.json"
    completed_new = 0
    banned_models = set()
    failed_debates: list[tuple] = []

    if estimate_time:
        median_sec, hist_n = _historical_debate_durations(Path("results"))
        per_debate_sec = median_sec if median_sec is not None else 60.0
        est_total_sec = per_debate_sec * total_runs
        buffered_sec = est_total_sec * 1.15  # 15% cushion for network variance
        median_label = f"{_format_duration(per_debate_sec)} per debate"
        if hist_n:
            median_label += f" (median of {hist_n} recent debates)"
        else:
            median_label += " (heuristic default)"
        console.print(
            f"[cyan]Estimated wall time:[/cyan] ~{_format_duration(buffered_sec)} "
            f"(planned {total_runs} debates; {median_label})"
        )

    def write_progress():
        payload = {
            "run_tag": run_tag,
            "debates_file": str(debates_path),
            "total_planned_remaining": total_runs,
            "completed_new": completed_new,
            "completed_prior": existing_completed,
            "completed_total": existing_completed + completed_new,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "banned_models": sorted(banned_models),
        }
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with progress_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    write_progress()

    if dry_run:
        judge_calls = total_runs * main_cfg.num_judges
        total_debater_cost, per_model_cost, total_judge_cost, per_judge_cost = _estimate_cost(
            debater_models, judge_models, main_cfg.rounds, len(topics_selected), debates_per_pair, balanced_sides, pairs
        )
        console.print("[green]Dry run (no debates executed).[/green]")
        console.print(
            f"Topics={len(topics_selected)}, Debaters={len(debater_models)}, Judges={len(judge_models)}, "
            f"Debates planned={total_runs}, Judge calls={judge_calls}"
        )
        console.print("Debater models:")
        for m in debater_models:
            console.print(f"  - {m.id} ({m.model}) max_tokens={m.token_limit}")
        console.print("Judge models:")
        for j in judge_models:
            console.print(f"  - {j.id} ({j.model}) max_tokens={j.token_limit}")
        approx_total = total_debater_cost + total_judge_cost
        console.print(
            f"Estimated cost (very rough, USD): debaters ~${total_debater_cost:.2f}, judges ~${total_judge_cost:.2f}, total ~${approx_total:.2f}"
        )
        missing_models = {
            m.model for m in debater_models if m.id not in per_model_cost
        } | {
            j.model for j in judge_models if j.id not in per_judge_cost
        }
        if missing_models:
            console.print(f"[yellow]Pricing unavailable for: {', '.join(sorted(missing_models))} (not in OpenRouter catalog response); omitted from estimate.[/yellow]")
        console.print("Per-debater share (approx):")
        for mid, cost in sorted(per_model_cost.items(), key=lambda kv: kv[1], reverse=True):
            console.print(f"  {mid}: ~${cost:.2f}")
        console.print("Per-judge share (approx):")
        for jid, cost in sorted(per_judge_cost.items(), key=lambda kv: kv[1], reverse=True):
            console.print(f"  {jid}: ~${cost:.2f}")
        # Build a full schedule preview with per-debate judge sampling (matches run-time logic)
        preview_usage = judge_usage.copy()
        schedule_preview = []
        for topic in topics_selected:
            for (model_a, model_b) in pairs:
                for rep in range(debates_per_pair):
                    debate_seed = derive_debate_seed(run_tag, topic.id, model_a.id, model_b.id, rep)
                    debate_rng = random.Random(debate_seed)
                    pro_model = model_a
                    con_model = model_b
                    if (not balanced_sides) and swap_sides and debate_rng.random() < 0.5:
                        pro_model, con_model = con_model, pro_model
                    judge_source_pool = list(judge_models)
                    if judges_from_selection:
                        judge_source_pool = [j for j in judge_models if j.id not in {pro_model.id, con_model.id}]
                    judges_chosen = []
                    if main_cfg.num_judges > 0:
                        if len(judge_source_pool) < main_cfg.num_judges:
                            judges_chosen = ["<insufficient judges after exclusion>"]
                        else:
                            panel = select_judges(
                                judge_source_pool, main_cfg.num_judges, debate_seed, preview_usage
                            )
                            judges_chosen = [j.id for j in panel]
                            for j in panel:
                                preview_usage[j.id] = preview_usage.get(j.id, 0) + 1
                    schedule_preview.append(
                        {
                            "topic": topic.id,
                            "pro": pro_model.id,
                            "con": con_model.id,
                            "judges": judges_chosen,
                            "rep": rep,
                        }
                    )
        sched_path = run_dir / "dryrun_schedule.json"
        with sched_path.open("w", encoding="utf-8") as f:
            json.dump(schedule_preview, f, indent=2)
        console.print(f"Saved full debate/judge schedule preview to {sched_path}")
        console.print("First 10 debates:")
        for i, entry in enumerate(schedule_preview[:10], start=1):
            console.print(
                f"  {i}. Topic {entry['topic']}: PRO={entry['pro']} vs CON={entry['con']} | judges={', '.join(entry['judges']) if entry['judges'] else 'n/a'}"
            )
        console.print(f"Output would be written to: debates={debates_path}, viz={viz_dir}, plots={plots_dir}")
        return

    run_index = 0
    for topic in topics_selected:
        for (model_a, model_b) in pairs:
            if model_a.id in banned_models or model_b.id in banned_models:
                continue
            key = (topic.id, model_a.id, model_b.id)
            already_done = completed_counts.get(key, 0)
            if already_done >= debates_per_pair:
                continue
            for rep in range(already_done, debates_per_pair):
                run_index += 1
                debate_seed = derive_debate_seed(run_tag, topic.id, model_a.id, model_b.id, rep)
                debate_rng = random.Random(debate_seed)
                pro_model = model_a
                con_model = model_b
                if (not balanced_sides) and swap_sides and debate_rng.random() < 0.5:
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

                    judge_source_pool = list(judge_models)
                    # If judges are drawn from the debater set, exclude the two active debaters for this debate.
                    if judges_from_selection:
                        judge_source_pool = [j for j in judge_models if j.id not in {pro_model.id, con_model.id}]
                    panel_configs = select_judges(
                        judge_source_pool, main_cfg.num_judges, debate_seed, judge_usage
                    )
                    panel_adapters = [judge_adapters[j.id] for j in panel_configs]
                    # Build candidate list: selected panel first, then remaining pool (balanced order)
                    remaining_candidates = [
                        j
                        for j in judge_source_pool
                        if j.id not in {cfg.id for cfg in panel_configs}
                    ]
                    remaining_adapters = [judge_adapters[j.id] for j in remaining_candidates]

                    console.print(
                        f"  Judging with panel: {', '.join(j.id for j in panel_configs)}"
                    )
                    judge_results, aggregate = run_judge_panel(
                        candidate_adapters=panel_adapters + remaining_adapters,
                        transcript=transcript,
                        config=main_cfg,
                        expected=main_cfg.num_judges,
                        usage=judge_usage,
                        seed=debate_seed,
                        log=log,
                    )

                    panel_latency = sum(j.latency_ms for j in judge_results if j.latency_ms is not None)
                    record = DebateRecord(
                        transcript=transcript,
                        judges=judge_results,
                        aggregate=aggregate,
                        created_at=datetime.now(timezone.utc),
                        judges_expected=main_cfg.num_judges,
                        judges_actual=len(judge_results),
                        panel_complete=len(judge_results) == main_cfg.num_judges,
                        panel_latency_ms=panel_latency,
                        debate_seed=debate_seed,
                        elo=main_cfg.elo,
                    )
                    append_debate_record(debates_path, record)
                    completed_counts[key] = completed_counts.get(key, 0) + 1
                    completed_new += 1
                    write_progress()
                    elapsed = (time.perf_counter() - t0) * 1000

                    console.print(
                        f"[cyan]{run_index}/{total_runs}[/cyan] "
                        f"Topic '{topic.id}' {pro_model.id} (Pro) vs {con_model.id} (Con) "
                        f"-> winner: {aggregate.winner} ({elapsed:.0f} ms)"
                    )
                except EmptyResponseError as e:
                    console.print(
                        f"[red]Debate failed ({pro_model.id} vs {con_model.id} on {topic.id}): {e}"
                    )
                    if skip_on_empty:
                        banned_models.add(e.model_id)
                        console.print(f"[yellow]Skipping model {e.model_id} for remainder of run due to empty responses.[/yellow]")
                        write_progress()
                    else:
                        failed_debates.append((topic, pro_model, con_model, rep))
                except Exception as e:
                    console.print(f"[red]Debate failed ({pro_model.id} vs {con_model.id} on {topic.id}): {e}")
                    failed_debates.append((topic, pro_model, con_model, rep))

    if retry_failed and failed_debates:
        console.print(f"[yellow]Retrying {len(failed_debates)} failed debates once...[/yellow]")
        retry_list = list(failed_debates)
        failed_debates = []
        for topic, model_a, model_b, rep in retry_list:
            if model_a.id in banned_models or model_b.id in banned_models:
                continue
            key = (topic.id, model_a.id, model_b.id)
            if completed_counts.get(key, 0) >= debates_per_pair:
                continue
            retry_seed = derive_debate_seed(run_tag, topic.id, model_a.id, model_b.id, rep) + 17
            debate_rng = random.Random(retry_seed)
            pro_model = model_a
            con_model = model_b
            if (not balanced_sides) and swap_sides and debate_rng.random() < 0.5:
                pro_model, con_model = con_model, pro_model

            pro_adapter = debater_adapters[pro_model.id]
            con_adapter = debater_adapters[con_model.id]

            try:
                t0 = time.perf_counter()
                transcript = run_debate(
                    topic=topic,
                    pro_adapter=pro_adapter,
                    con_adapter=con_adapter,
                    config=main_cfg,
                    seed=seed,
                    log=console.print,
                )

                judge_source_pool = list(judge_models)
                if judges_from_selection:
                    judge_source_pool = [j for j in judge_models if j.id not in {pro_model.id, con_model.id}]
                panel_configs = select_judges(
                    judge_source_pool, main_cfg.num_judges, retry_seed, judge_usage
                )
                remaining_candidates = [
                    j for j in judge_source_pool if j.id not in {cfg.id for cfg in panel_configs}
                ]
                panel_adapters = [judge_adapters[j.id] for j in panel_configs]
                remaining_adapters = [judge_adapters[j.id] for j in remaining_candidates]

                judge_results, aggregate = run_judge_panel(
                    candidate_adapters=panel_adapters + remaining_adapters,
                    transcript=transcript,
                    config=main_cfg,
                    expected=main_cfg.num_judges,
                    usage=judge_usage,
                    seed=retry_seed,
                    log=console.print,
                )

                panel_latency = sum(j.latency_ms for j in judge_results if j.latency_ms is not None)
                record = DebateRecord(
                    transcript=transcript,
                    judges=judge_results,
                    aggregate=aggregate,
                    created_at=datetime.now(timezone.utc),
                    judges_expected=main_cfg.num_judges,
                    judges_actual=len(judge_results),
                    panel_complete=len(judge_results) == main_cfg.num_judges,
                    panel_latency_ms=panel_latency,
                    debate_seed=retry_seed,
                    elo=main_cfg.elo,
                )
                append_debate_record(debates_path, record)
                completed_counts[key] = completed_counts.get(key, 0) + 1
                completed_new += 1
                write_progress()
                elapsed = (time.perf_counter() - t0) * 1000
                console.print(
                    f"[green]Retry success[/green] Topic '{topic.id}' {pro_model.id} vs {con_model.id} -> {aggregate.winner} ({elapsed:.0f} ms)"
                )
            except Exception as e:
                console.print(f"[red]Retry failed ({pro_model.id} vs {con_model.id} on {topic.id}): {e}")

    console.print(f"[green]Run complete. Writing summaries to {viz_dir} and plots to {plots_dir}")
    summarize(debates_path=debates_path, out_dir=viz_dir)
    plot_command(viz_dir=viz_dir, out_dir=plots_dir)
    if postrate:
        console.print(f"[cyan]Recomputing ratings and showing leaderboard (top 10).[/cyan]")
        rate_command(debates_path=debates_path, config_path=config_path, ratings_path=ratings_path)
        show_leaderboard(ratings_path=ratings_path, top=10)


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
    debate_id: Optional[str] = typer.Argument(
        None, help="Debate ID to inspect (omit to show the latest debate)."
    ),
    debates_path: Path = typer.Option(
        Path("results/debates.jsonl"), help="Path to debates file."
    ),
    latest: bool = typer.Option(
        False,
        "--latest",
        help="Automatically pick the newest debates_*.jsonl file and the newest debate ID.",
    ),
):
    """
    Print a single debate and its judge decisions.
    """
    def _find_latest_debates_file() -> Optional[Path]:
        results_dir = Path("results")
        candidates = list(results_dir.glob("debates_*.jsonl"))
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]
        default = results_dir / "debates.jsonl"
        return default if default.exists() else None

    path_in = debates_path
    if latest or debate_id is None:
        auto = _find_latest_debates_file()
        if auto:
            path_in = auto

    debates = load_debate_records(path_in)
    if not debates:
        console.print(f"[red]No debates found at {path_in}")
        raise typer.Exit(code=1)

    record = None
    if debate_id:
        matches = [d for d in debates if d.transcript.debate_id == debate_id]
        if matches:
            record = matches[0]
    else:
        try:
            record = max(debates, key=lambda d: d.created_at)
        except Exception:
            record = debates[-1] if debates else None

    if record is None:
        console.print(f"[red]Debate {debate_id or ''} not found in {path_in}")
        raise typer.Exit(code=1)

    console.print(f"[green]Using debates file: {path_in}")
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


@app.command("upload-results")
def upload_results_command(
    source: Path = typer.Option(
        Path("results"), help="File or directory to upload recursively."
    ),
    bucket: str = typer.Option(..., help="Destination S3 bucket name."),
    prefix: str = typer.Option(
        "", help="Key prefix inside the bucket (omit leading slash)."
    ),
    profile: Optional[str] = typer.Option(
        None, help="AWS profile name to use (falls back to env/default)."
    ),
    region: Optional[str] = typer.Option(
        None, help="AWS region override (otherwise boto3 default chain)."
    ),
    dry_run: bool = typer.Option(False, help="List uploads without sending."),
):
    """
    Upload a file or an entire directory tree to S3 for safekeeping.

    Credentials are taken from the standard AWS chain (env vars, shared
    credentials/config, or the provided --profile). Server-side encryption uses
    AWS-managed keys (SSE-S3) by default.
    """
    if not source.exists():
        raise typer.BadParameter(f"Source not found: {source}")

    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region
    session = boto3.Session(**session_kwargs)
    s3 = session.client("s3")

    files: list[tuple[Path, str]] = []
    if source.is_file():
        rel = source.name
        key = "/".join([p for p in [prefix, rel] if p])
        files.append((source, key))
    else:
        for path in source.rglob("*"):
            if path.is_file():
                rel = path.relative_to(source)
                key = "/".join([p for p in [prefix, rel.as_posix()] if p])
                files.append((path, key))

    if not files:
        console.print(f"[yellow]No files to upload under {source}.[/yellow]")
        return

    console.print(f"[cyan]Prepared {len(files)} uploads to s3://{bucket}/{prefix or ''}[/cyan]")
    if dry_run:
        for p, k in files:
            console.print(f"DRY-RUN {p} -> s3://{bucket}/{k}")
        return

    for idx, (path, key) in enumerate(files, start=1):
        console.print(f"[blue]{idx}/{len(files)}[/blue] {path} -> s3://{bucket}/{key}")
        try:
            s3.upload_file(
                Filename=str(path),
                Bucket=bucket,
                Key=key,
                ExtraArgs={"ServerSideEncryption": "AES256"},
            )
        except (BotoCoreError, NoCredentialsError) as e:
            raise typer.BadParameter(f"AWS upload failed: {e}") from e

    console.print(f"[green]Uploaded {len(files)} files to s3://{bucket}/{prefix or ''}[/green]")


def main():
    app(prog_name="debatebench")


if __name__ == "__main__":
    main()
