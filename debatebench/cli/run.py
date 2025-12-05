"""Run command and supporting helpers for DebateBench."""
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

from .. import config as cfg
from ..debate import run_debate, EmptyResponseError
from ..judge import run_judge_panel
from ..models import build_debater_adapter, build_judge_adapter, sample_judges
from ..openrouter import fetch_recent_openrouter_models, probe_model
from ..schema import DebateRecord, DebaterModelConfig, JudgeModelConfig
from ..storage import append_debate_record, load_debate_records
from ..settings import load_settings
from .common import console
from .rate import rate_command
from .leaderboard import show_leaderboard
from .summarize import summarize
from .plot import plot_command
from collections import defaultdict


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
    openrouter_max_tokens: Optional[int] = typer.Option(
        None, help="Max tokens per debater completion when using OpenRouter models (None = no cap)."
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
    openrouter_judge_max_tokens: Optional[int] = typer.Option(
        None, help="Max tokens per judge completion when using OpenRouter models (None = no cap)."
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
        False,
        help="Apply fixed per-stage token limits (disabled by default; leave off for uncapped turns).",
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
        hidden=True,
        help="Deprecated; token limits are fixed to 1000 (debaters) and 400 (judges).",
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
    log_failed_judges: bool = typer.Option(
        False,
        help="If set, write raw responses for dropped judges to run_<tag>/failed_judges.jsonl for debugging.",
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

    # Apply per-stage token limits only if explicitly requested
    if apply_stage_token_limits:
        stage_limits = {"opening": openrouter_max_tokens, "rebuttal": openrouter_max_tokens, "closing": openrouter_max_tokens}
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
    judge_output_max_tokens = openrouter_judge_max_tokens

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
                parameters={"temperature": 0.35 if openrouter_temperature is None else openrouter_temperature},
            ),
            DebaterModelConfig(
                id="openai-gpt-5.1",
                provider="openrouter",
                model="openai/gpt-5.1",
                token_limit=openrouter_max_tokens,
                endpoint=None,
                parameters={"temperature": 0.35 if openrouter_temperature is None else openrouter_temperature},
            ),
        ]
        judge_models = [
            JudgeModelConfig(
                id="moonshotai-kimi-k2",
                provider="openrouter",
                model="moonshotai/kimi-k2",
                token_limit=judge_output_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": 0.0 if openrouter_temperature is None else openrouter_temperature},
            ),
            JudgeModelConfig(
                id="anthropic-claude-opus-4.5",
                provider="openrouter",
                model="anthropic/claude-opus-4.5",
                token_limit=judge_output_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": 0.0 if openrouter_temperature is None else openrouter_temperature},
            ),
            JudgeModelConfig(
                id="deepseek-deepseek-v3.2",
                provider="openrouter",
                model="deepseek/deepseek-v3.2",
                token_limit=judge_output_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": 0.0 if openrouter_temperature is None else openrouter_temperature},
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

    # Leave token limits as provided (caps optional)

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

    def _load_activity_pricing(activity_path: Optional[Path] = None) -> Tuple[Dict[str, Tuple[float, float]], Optional[Path]]:
        """
        Build per-model prompt/completion token rates from an OpenRouter activity JSON.
        Uses a blended rate: usage / (prompt+completion+reasoning tokens).
        """
        if activity_path is None:
            candidates = sorted(Path("results").glob("openrouter_activity_*.json"))
            if not candidates:
                return {}, None
            activity_path = candidates[-1]
        if not activity_path.exists():
            return {}, None

        try:
            raw = json.loads(activity_path.read_text())
            records = raw.get("data") if isinstance(raw, dict) else raw
        except Exception:
            return {}, None
        if not isinstance(records, list):
            return {}, None

        agg: Dict[str, Dict[str, float]] = {}
        for rec in records:
            try:
                model = rec.get("model") or rec.get("model_permaslug")
                usage = float(rec.get("usage", 0) or 0.0)
                pt = int(rec.get("prompt_tokens", 0) or 0)
                ct = int(rec.get("completion_tokens", 0) or 0)
                rt = int(rec.get("reasoning_tokens", 0) or 0)
            except Exception:
                continue
            if not model or usage <= 0:
                continue
            bucket = agg.setdefault(model, {"usage": 0.0, "pt": 0, "ct": 0, "rt": 0})
            bucket["usage"] += usage
            bucket["pt"] += pt
            bucket["ct"] += ct
            bucket["rt"] += rt

        pricing: Dict[str, Tuple[float, float]] = {}
        for model, vals in agg.items():
            total_tokens = vals["pt"] + vals["ct"] + vals["rt"]
            if total_tokens <= 0:
                continue
            rate = vals["usage"] / total_tokens
            pricing[model] = (rate, rate)
        return pricing, activity_path

    def _load_token_stats(debates_path: Optional[Path] = None):
        """
        Load historical average prompt/completion tokens per debater and judge from the
        most recent debates_*.jsonl (or a specific path if provided).
        Returns (debater_stats, judge_stats, source_path)
        debater_stats: model_id -> {"prompt_avg": float, "completion_avg": float}
        judge_stats: judge_id -> {"prompt_avg": float, "completion_avg": float}
        """
        if debates_path is None:
            candidates = sorted(Path("results").glob("debates_*.jsonl"), key=lambda p: p.stat().st_mtime)
            if not candidates:
                return {}, {}, None
            debates_path = candidates[-1]

        debater_totals: Dict[str, Dict[str, float]] = {}
        debater_counts: Dict[str, int] = {}
        judge_totals: Dict[str, Dict[str, float]] = {}
        judge_counts: Dict[str, int] = {}
        judge_samples: Dict[str, Dict[str, list[float]]] = {}

        try:
            with debates_path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    tr = rec.get("transcript") or {}
                    for turn in tr.get("turns", []):
                        pt = turn.get("prompt_tokens")
                        ct = turn.get("completion_tokens")
                        if pt is None or ct is None:
                            continue
                        speaker = turn.get("speaker")
                        mid = tr.get("pro_model_id") if speaker == "pro" else tr.get("con_model_id")
                        if not mid:
                            continue
                        agg = debater_totals.setdefault(mid, {"pt": 0.0, "ct": 0.0})
                        agg["pt"] += pt
                        agg["ct"] += ct
                        debater_counts[mid] = debater_counts.get(mid, 0) + 1
                    for jres in rec.get("judges", []):
                        pid = jres.get("judge_id")
                        pt = jres.get("prompt_tokens")
                        ct = jres.get("completion_tokens")
                        if pid is None or pt is None or ct is None:
                            continue
                        agg = judge_totals.setdefault(pid, {"pt": 0.0, "ct": 0.0})
                        agg["pt"] += pt
                        agg["ct"] += ct
                        judge_counts[pid] = judge_counts.get(pid, 0) + 1
                        samples = judge_samples.setdefault(pid, {"pt": [], "ct": []})
                        samples["pt"].append(pt)
                        samples["ct"].append(ct)
        except Exception:
            return {}, {}, None

        debater_stats = {}
        for mid, totals in debater_totals.items():
            n = debater_counts.get(mid, 0)
            if n:
                debater_stats[mid] = {
                    "prompt_avg": totals["pt"] / n,
                    "completion_avg": totals["ct"] / n,
                }
        judge_stats = {}
        for pid, totals in judge_totals.items():
            n = judge_counts.get(pid, 0)
            if n:
                # Use a low percentile (10th) to stay conservative for judges and cap prompts/completions.
                def pct(vals: list[float], p: float) -> float:
                    if not vals:
                        return 0.0
                    s = sorted(vals)
                    if len(s) == 1:
                        return s[0]
                    idx = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
                    return s[idx]

                def median(vals: list[float]) -> float:
                    if not vals:
                        return 0.0
                    s = sorted(vals)
                    k = len(s)
                    mid = k // 2
                    if k % 2:
                        return s[mid]
                    return 0.5 * (s[mid - 1] + s[mid])

                samples = judge_samples.get(pid, {"pt": [], "ct": []})
                prompt_raw = pct(samples.get("pt", []), 0.10) if samples.get("pt") else totals["pt"] / n
                completion_raw = pct(samples.get("ct", []), 0.10) if samples.get("ct") else totals["ct"] / n
                prompt_med = median(samples.get("pt", [])) if samples.get("pt") else prompt_raw
                completion_med = median(samples.get("ct", [])) if samples.get("ct") else completion_raw
                # Cap with median and tightened ceilings to avoid overestimation from heavy judges.
                prompt_capped = min(prompt_raw, prompt_med, 1500.0)
                completion_capped = min(completion_raw, completion_med, 250.0)
                judge_stats[pid] = {
                    "prompt_avg": prompt_capped,
                    "completion_avg": completion_capped,
                }
        return debater_stats, judge_stats, debates_path

    def _estimate_cost(
        debaters,
        judges,
        rounds,
        num_topics,
        debates_per_pair,
        balanced,
        pairs,
        pricing_override: Optional[Dict[str, Tuple[float, float]]] = None,
        token_stats: Optional[Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]] = None,
    ) -> Tuple[float, Dict[str, float], float, Dict[str, float]]:
        """
        Rough cost estimator using live OpenRouter pricing (USD per token) when available.
        Token model:
          - Debater: completion tokens = sum(token_limit for its stages); prompt tokens ~= sum(history before each turn)
            approximated as completion_total + (completion_total - first_turn_tokens)
          - Judge: prompt tokens = sum(token_limit for all turns); completion ~200 tokens JSON
        """
        models_needed = {m.model for m in debaters} | {j.model for j in judges}
        pricing = pricing_override or _fetch_pricing(models_needed)

        def side_token_budget():
            limits = [r.token_limit for r in rounds if r.speaker == "pro"]
            limits = [l for l in limits if isinstance(l, (int, float))]
            if not limits:
                return 0, 0
            comp = sum(limits)
            first_turn = limits[0]
            prompt = comp + max(0, comp - first_turn)
            return prompt, comp
        turns_per_side = len([r for r in rounds if r.speaker == "pro"])

        prompt_side, comp_side = side_token_budget()
        debater_stats = token_stats[0] if token_stats else {}
        judge_stats = token_stats[1] if token_stats else {}
        per_model_cost: Dict[str, float] = {}
        total_debater_cost = 0.0
        debates_per_pair_total = debates_per_pair * num_topics
        for a, b in pairs:
            for model, tokens in ((a, (prompt_side, comp_side)), (b, (prompt_side, comp_side))):
                if model.id in debater_stats:
                    # Use historical per-turn averages instead of token limits
                    prompt_tokens = debater_stats[model.id]["prompt_avg"] * turns_per_side
                    comp_tokens = debater_stats[model.id]["completion_avg"] * turns_per_side
                else:
                    prompt_tokens, comp_tokens = tokens
                rates = pricing.get(model.model)
                if not rates:
                    continue
                p_rate, c_rate = rates
                cost = prompt_tokens * p_rate + comp_tokens * c_rate
                per_model_cost[model.id] = per_model_cost.get(model.id, 0.0) + cost * debates_per_pair_total
                total_debater_cost += cost * debates_per_pair_total

        transcript_tokens = sum(r.token_limit for r in rounds if isinstance(r.token_limit, (int, float)))
        judge_output_tokens = 200
        per_judge_cost: Dict[str, float] = {}
        total_judge_cost = 0.0
        judge_calls = len(pairs) * debates_per_pair_total
        for j in judges:
            if j.id in judge_stats:
                prompt_tokens = judge_stats[j.id]["prompt_avg"]
                comp_tokens = judge_stats[j.id]["completion_avg"]
            else:
                prompt_tokens = transcript_tokens
                comp_tokens = judge_output_tokens
            rates = pricing.get(j.model)
            if not rates:
                continue
            p_rate, c_rate = rates
            cost = prompt_tokens * p_rate + comp_tokens * c_rate
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
    failed_judges_path = run_dir / "failed_judges.jsonl" if log_failed_judges else None

    if dry_run:
        judge_calls = total_runs * main_cfg.num_judges
        # Prefer activity-derived pricing (last 30 days) and fall back to live catalog for gaps.
        activity_pricing, activity_path = _load_activity_pricing()
        models_needed = {m.model for m in debater_models} | {j.model for j in judge_models}
        pricing_map = _fetch_pricing(models_needed)
        pricing_source_label = "live (OpenRouter catalog)"
        if activity_pricing:
            pricing_map.update(activity_pricing)  # activity overrides live for better empirical averages
            if activity_path:
                pricing_source_label = f"activity ({activity_path.name}) + live fallback"
            else:
                pricing_source_label = "activity + live fallback"
        # Load historical token stats (latest debates_* file) to tighten cost estimates.
        deb_stats, judge_stats, stats_path = _load_token_stats()
        stats_label = f"turn averages from {stats_path.name}" if stats_path else "no historical token stats"
        total_debater_cost, per_model_cost, total_judge_cost, per_judge_cost = _estimate_cost(
            debater_models,
            judge_models,
            main_cfg.rounds,
            len(topics_selected),
            debates_per_pair,
            balanced_sides,
            pairs,
            pricing_override=pricing_map,
            token_stats=(deb_stats, judge_stats),
        )
        console.print("[green]Dry run (no debates executed).[/green]")
        console.print(f"[cyan]Cost pricing source:[/cyan] {pricing_source_label} | {stats_label}")
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
                    # Optional sink to capture failed judges
                    def sink_failed(payload):
                        if not failed_judges_path:
                            return
                        failed_judges_path.parent.mkdir(parents=True, exist_ok=True)
                        import json as _json

                        with failed_judges_path.open("a", encoding="utf-8") as f:
                            f.write(
                                _json.dumps(
                                    {
                                        **payload,
                                        "debate_id": transcript.debate_id,
                                        "topic": topic.id,
                                        "pro": pro_model.id,
                                        "con": con_model.id,
                                        "created_at": datetime.now(timezone.utc).isoformat(),
                                    }
                                )
                            )
                            f.write("\n")

                    judge_results, aggregate = run_judge_panel(
                        candidate_adapters=panel_adapters + remaining_adapters,
                        transcript=transcript,
                        config=main_cfg,
                        expected=main_cfg.num_judges,
                        usage=judge_usage,
                        seed=debate_seed,
                        log=log,
                        failed_judges_sink=sink_failed if failed_judges_path else None,
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
