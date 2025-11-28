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
from .debate import run_debate, EmptyResponseError
from .judge import run_judge_panel
from .models import build_debater_adapter, build_judge_adapter, sample_judges
from .openrouter import fetch_recent_openrouter_models, probe_model
from .rating import recompute_ratings
from .schema import DebateRecord, DebaterModelConfig, JudgeModelConfig
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
        None, help="Random seed for reproducibility."
    ),
    swap_sides: bool = typer.Option(
        False, help="Randomly swap Pro/Con assignment per debate (ignored if --balanced-sides)."
    ),
    balanced_sides: bool = typer.Option(
        True, help="Ensure each model pair plays both sides (permutations). Disable for combinations."
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
        512, help="Max tokens per debater completion when using OpenRouter models."
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
):
    """
    Run a batch of debates and append results.
    """
    main_cfg, topics, debater_models, judge_models = cfg.load_all_configs(
        config_path, topics_path, models_path, judges_path
    )

    # Apply default per-stage token limits if enabled
    if apply_stage_token_limits:
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
    viz_dir = Path("results") / f"viz_{run_tag}"
    plots_dir = Path("results") / f"plots_{run_tag}"

    if not topics:
        raise typer.BadParameter("Topics list is empty.")

    rng = random.Random(seed)
    settings = load_settings()

    topics_selected = topics

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
                parameters={"temperature": openrouter_temperature},
            ),
            DebaterModelConfig(
                id="openai-gpt-5.1",
                provider="openrouter",
                model="openai/gpt-5.1",
                token_limit=openrouter_max_tokens,
                endpoint=None,
                parameters={"temperature": openrouter_temperature},
            ),
        ]
        judge_models = [
            JudgeModelConfig(
                id="moonshotai-kimi-k2-thinking",
                provider="openrouter",
                model="moonshotai/kimi-k2-thinking",
                token_limit=openrouter_judge_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": openrouter_temperature},
            ),
            JudgeModelConfig(
                id="anthropic-claude-opus-4.5",
                provider="openrouter",
                model="anthropic/claude-opus-4.5",
                token_limit=openrouter_judge_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": openrouter_temperature},
            ),
            JudgeModelConfig(
                id="deepseek-deepseek-v3.2-exp",
                provider="openrouter",
                model="deepseek/deepseek-v3.2-exp",
                token_limit=openrouter_judge_max_tokens,
                endpoint=None,
                prompt_style=None,
                parameters={"temperature": openrouter_temperature},
            ),
        ]
        main_cfg.num_judges = 3
        console.print("[cyan]Quick test mode: 1 random topic, fixed debaters and judges.[/cyan]")
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
                            token_limit=openrouter_judge_max_tokens,
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
    banned_models = set()
    for topic in topics_selected:
        for (model_a, model_b) in pairs:
            if model_a.id in banned_models or model_b.id in banned_models:
                continue
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
                except EmptyResponseError as e:
                    console.print(
                        f"[red]Debate failed ({pro_model.id} vs {con_model.id} on {topic.id}): {e}"
                    )
                    if skip_on_empty:
                        banned_models.add(e.model_id)
                        console.print(f"[yellow]Skipping model {e.model_id} for remainder of run due to empty responses.[/yellow]")
                    else:
                        raise
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
