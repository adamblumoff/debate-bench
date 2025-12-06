"""Run command and supporting helpers for DebateBench."""
from __future__ import annotations

import json
import random
import shutil
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from ... import config as cfg
from ...debate import EmptyResponseError, run_debate
from ...judge import run_judge_panel
from ...models import build_debater_adapter, build_judge_adapter
from ...openrouter import fetch_recent_openrouter_models, probe_model
from ...schema import DebateRecord, DebaterModelConfig, JudgeModelConfig
from ...settings import load_settings
from ...storage import append_debate_record, load_debate_records
from ..common import console
from ..leaderboard import show_leaderboard
from ..plot import plot_command
from ..rate import rate_command
from ..summarize import summarize
from .estimate import (
    estimate_cost,
    fetch_pricing,
    format_duration,
    historical_debate_durations,
    load_activity_pricing,
    load_token_stats,
)
from .schedule import build_pairs, derive_debate_seed, select_judges
from .selection import (
    SelectionCancelled,
    _fallback_select_models,
    _fallback_select_topics,
    _interactive_select_models,
    _interactive_select_topics,
    selection_wizard,
)


def _slugify_model_id(model_id: str) -> str:
    """Filesystem-friendly identifier for snapshot artifacts."""
    return model_id.replace("/", "-").replace(" ", "_")


def _infer_debates_per_pair(records: list[DebateRecord]):
    """
    Infer the per-topic, per-ordered-pair debate count from an existing debates file.
    Returns (most_common_count, anomalies_dict).
    """
    counts = Counter()
    for rec in records:
        key = (rec.transcript.topic.id, rec.transcript.pro_model_id, rec.transcript.con_model_id)
        counts[key] += 1
    if not counts:
        return None, {}
    # Most common value across pairs/topics
    common_count, _ = Counter(counts.values()).most_common(1)[0]
    anomalies = {k: v for k, v in counts.items() if v != common_count}
    return common_count, anomalies


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
    new_model_id: Optional[str] = typer.Option(
        None,
        "--new-model",
        help="Append a single new debater against the incumbents from an existing run tag.",
    ),
    sample_topics: Optional[int] = typer.Option(
        None, help="Number of topics to sample (default all)."
    ),
    debates_per_pair: Optional[int] = typer.Option(
        None,
        help="Number of debates per model pair per topic. Defaults to 1, or to the inferred value from --run-tag when using --new-model.",
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
    main_cfg, topics_cfg, config_debater_models, config_judge_models = cfg.load_all_configs(
        config_path, topics_path, models_path, judges_path
    )
    topics = topics_cfg
    debater_models = config_debater_models
    judge_models = config_judge_models

    incremental_mode = new_model_id is not None

    # derive run tag and output paths (timestamp when omitted)
    if incremental_mode and not run_tag:
        raise typer.BadParameter("--new-model requires --run-tag pointing to an existing debates_<tag>.jsonl file.")
    if not run_tag:
        run_tag = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
    debates_path = debates_path.parent / f"debates_{run_tag}.jsonl"
    if incremental_mode and not debates_path.exists():
        raise typer.BadParameter(f"--new-model expects an existing debates file for run tag '{run_tag}' at {debates_path}.")

    run_dir = Path("results") / f"run_{run_tag}"
    viz_dir = Path("results") / f"viz_{run_tag}"
    plots_dir = Path("results") / f"plots_{run_tag}"
    ratings_path = Path("results") / f"ratings_{run_tag}.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = run_dir / "config_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    append_slug = _slugify_model_id(new_model_id) if incremental_mode and new_model_id else None
    cli_args_path = snapshot_dir / (
        "cli_args.json" if not incremental_mode else f"cli_args_append_{append_slug}.json"
    )
    selection_snapshot_path = snapshot_dir / (
        "effective_selection.json" if not incremental_mode else f"effective_selection_append_{append_slug}.json"
    )
    # Preserve input config files and CLI args for reproducibility (avoid clobbering baseline when appending).
    for src in (config_path, topics_path, models_path, judges_path):
        try:
            dest = snapshot_dir / src.name
            if incremental_mode and dest.exists():
                continue
            shutil.copy(src, dest)
        except FileNotFoundError:
            pass

    if (not topics) and (not incremental_mode):
        raise typer.BadParameter("Topics list is empty.")

    rng = random.Random(seed)
    settings = load_settings()

    topics_selected = topics
    judge_output_max_tokens = openrouter_judge_max_tokens
    existing_records: list[DebateRecord] = []
    base_cli_args: dict = {}

    if incremental_mode:
        if quick_test or judges_test:
            raise typer.BadParameter("--new-model cannot be combined with --quick-test or --judges-test.")
        base_selection_file = snapshot_dir / "effective_selection.json"
        base_cli_args_path = snapshot_dir / "cli_args.json"
        if not base_selection_file.exists():
            raise typer.BadParameter(f"Base selection snapshot missing: {base_selection_file}.")
        if not base_cli_args_path.exists():
            raise typer.BadParameter(f"Base CLI snapshot missing: {base_cli_args_path}.")
        with base_selection_file.open("r", encoding="utf-8") as f:
            base_selection = json.load(f)
        with base_cli_args_path.open("r", encoding="utf-8") as f:
            base_cli_args = json.load(f)
        try:
            main_cfg = cfg.MainConfig(**base_selection["main_config"])
        except Exception as e:  # pylint: disable=broad-except
            raise typer.BadParameter(f"Failed to load main config from {base_selection_file}: {e}") from e
        topics_selected = [cfg.Topic(**t) for t in base_selection.get("topics_selected", [])]
        incumbent_models = [DebaterModelConfig(**m) for m in base_selection.get("debater_models", [])]
        judge_models = [JudgeModelConfig(**j) for j in base_selection.get("judge_models", [])]
        if not incumbent_models:
            raise typer.BadParameter(f"No debaters found in baseline snapshot {base_selection_file}.")

        existing_records = load_debate_records(debates_path)
        if not existing_records:
            raise typer.BadParameter(f"Existing debates file {debates_path} is empty; cannot infer prior schedule.")
        # Mirror topics actually used in the baseline log to avoid drift.
        topics_in_log = []
        seen_topics = set()
        for rec in existing_records:
            t = rec.transcript.topic
            if t.id not in seen_topics:
                topics_in_log.append(cfg.Topic(**t.dict()))
                seen_topics.add(t.id)
        topics_selected = topics_in_log
        if not topics_selected:
            raise typer.BadParameter(f"No topics found in debates file {debates_path}.")
        inferred_per_pair, anomalies = _infer_debates_per_pair(existing_records)
        base_cli_per_pair = base_cli_args.get("debates_per_pair")
        if debates_per_pair is None:
            debates_per_pair = base_cli_per_pair or inferred_per_pair or 1
        if base_cli_per_pair and inferred_per_pair and base_cli_per_pair != inferred_per_pair:
            console.print(
                f"[yellow]Planned debates_per_pair={base_cli_per_pair} but observed {inferred_per_pair} in log; using observed value.[/yellow]"
            )
            debates_per_pair = inferred_per_pair
        if anomalies:
            # Show up to 3 anomalies for visibility.
            preview = list(anomalies.items())[:3]
            details = ", ".join(f"{k[1]} vs {k[2]} on {k[0]} -> {v}" for k, v in preview)
            console.print(
                f"[yellow]Uneven prior debate counts detected ({len(anomalies)} anomalies). "
                f"Continuing with existing counts; sample: {details}[/yellow]"
            )

        balanced_sides = base_cli_args.get("balanced_sides", balanced_sides)
        swap_sides = base_cli_args.get("swap_sides", swap_sides)
        balanced_judges = base_cli_args.get("balanced_judges", balanced_judges)
        judges_from_selection = base_cli_args.get("judges_from_selection", judges_from_selection)
        apply_stage_token_limits = base_cli_args.get("apply_stage_token_limits", apply_stage_token_limits)
        openrouter_max_tokens = base_cli_args.get("openrouter_max_tokens", openrouter_max_tokens)
        openrouter_judge_max_tokens = base_cli_args.get("openrouter_judge_max_tokens", openrouter_judge_max_tokens)
        judge_output_max_tokens = openrouter_judge_max_tokens

        new_model_cfg = next((m for m in config_debater_models if m.id == new_model_id), None)
        if new_model_cfg is None:
            raise typer.BadParameter(f"New model id '{new_model_id}' not found in {models_path}.")
        combined_models = []
        seen_ids = set()
        for m in incumbent_models + [new_model_cfg]:
            if m.id in seen_ids:
                continue
            seen_ids.add(m.id)
            combined_models.append(m)
        debater_models = combined_models
        existing_new = sum(
            1 for rec in existing_records if rec.transcript.pro_model_id == new_model_id or rec.transcript.con_model_id == new_model_id
        )
        console.print(
            f"[cyan]Incremental mode:[/cyan] base run '{run_tag}' with {len(topics_selected)} topics, "
            f"{len(incumbent_models)} incumbents; scheduling {debates_per_pair} debate(s) per ordered pair per topic for new model '{new_model_id}'."
        )
        if existing_new:
            console.print(
                f"[yellow]Detected {existing_new} existing debates with {new_model_id}; counts will be reused so only missing matchups are scheduled.[/yellow]"
            )
    else:
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
                    parameters={"temperature": 0.35},
                ),
                DebaterModelConfig(
                    id="google-gemini-2.5-flash-lite-preview-09-2025",
                    provider="openrouter",
                    model="google/gemini-2.5-flash-lite-preview-09-2025",
                    token_limit=openrouter_max_tokens,
                    endpoint=None,
                    parameters={"temperature": 0.35},
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

    if debates_per_pair is None:
        if incremental_mode:
            raise typer.BadParameter("Could not infer debates_per_pair from the existing run; please provide --debates-per-pair.")
        debates_per_pair = 1

    # Apply per-stage token limits only if explicitly requested (after selections are finalized)
    if apply_stage_token_limits:
        stage_limits = {"opening": openrouter_max_tokens, "rebuttal": openrouter_max_tokens, "closing": openrouter_max_tokens}
        new_rounds = []
        for r in main_cfg.rounds:
            lim = stage_limits.get(r.stage, r.token_limit)
            new_rounds.append(r.copy(update={"token_limit": lim}))
        main_cfg.rounds = new_rounds

    # Persist CLI args for reproducibility (avoid clobbering baseline snapshot when appending)
    cli_args = {
        "config_path": str(config_path),
        "topics_path": str(topics_path),
        "models_path": str(models_path),
        "judges_path": str(judges_path),
        "debates_path_arg": str(debates_path),
        "run_tag": run_tag,
        "new_model_id": new_model_id,
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
        "resume": resume,
        "retry_failed": retry_failed,
        "dry_run": dry_run,
        "postrate": postrate,
    }
    with cli_args_path.open("w", encoding="utf-8") as f:
        json.dump(cli_args, f, indent=2)

    selection_snapshot = {
        "main_config": main_cfg.dict(),
        "topics_selected": [t.dict() for t in topics_selected],
        "debater_models": [m.dict() for m in debater_models],
        "judge_models": [j.dict() for j in judge_models],
    }
    with selection_snapshot_path.open("w", encoding="utf-8") as f:
        json.dump(selection_snapshot, f, indent=2)

    # Build adapters
    debater_adapters = {m.id: build_debater_adapter(m, settings) for m in debater_models}
    judge_adapters = {j.id: build_judge_adapter(j, settings) for j in judge_models}

    # Generate schedule of model pairs
    if incremental_mode:
        new_model_cfg = next((m for m in debater_models if m.id == new_model_id), None)
        if new_model_cfg is None:
            raise typer.BadParameter(f"New model '{new_model_id}' disappeared after selection.")
        incumbents = [m for m in debater_models if m.id != new_model_id]
        # Preserve baseline ordering/orientation by filtering the full pair set.
        combined_order = incumbents + [new_model_cfg]
        all_pairs = build_pairs(combined_order, balanced_sides)
        pairs = [p for p in all_pairs if new_model_id in {p[0].id, p[1].id}]
    else:
        pairs = build_pairs(debater_models, balanced_sides)
    completed_counts = defaultdict(int)
    judge_usage = defaultdict(int)
    existing = existing_records
    loaded_from_disk = False
    if (not existing) and resume and debates_path.exists():
        existing = load_debate_records(debates_path)
        loaded_from_disk = True
    if existing:
        for rec in existing:
            key = (rec.transcript.topic.id, rec.transcript.pro_model_id, rec.transcript.con_model_id)
            completed_counts[key] += 1
            for jres in rec.judges:
                judge_usage[jres.judge_id] += 1
        if incremental_mode:
            console.print(
                f"[cyan]Loaded {len(existing)} completed debates from {debates_path}; skipping already-finished pairings for incremental append.[/cyan]"
            )
        elif resume and loaded_from_disk:
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
        median_sec, hist_n = historical_debate_durations(Path("results"))
        per_debate_sec = median_sec if median_sec is not None else 60.0
        est_total_sec = per_debate_sec * total_runs
        buffered_sec = est_total_sec * 1.15  # 15% cushion for network variance
        median_label = f"{format_duration(per_debate_sec)} per debate"
        if hist_n:
            median_label += f" (median of {hist_n} recent debates)"
        else:
            median_label += " (heuristic default)"
        console.print(
            f"[cyan]Estimated wall time:[/cyan] ~{format_duration(buffered_sec)} "
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
        activity_pricing, activity_path = load_activity_pricing()
        models_needed = {m.model for m in debater_models} | {j.model for j in judge_models}
        pricing_map = fetch_pricing(models_needed, settings)
        pricing_source_label = "live (OpenRouter catalog)"
        if activity_pricing:
            pricing_map.update(activity_pricing)  # activity overrides live for better empirical averages
            if activity_path:
                pricing_source_label = f"activity ({activity_path.name}) + live fallback"
            else:
                pricing_source_label = "activity + live fallback"
        # Load historical token stats (latest debates_* file) to tighten cost estimates.
        deb_stats, judge_stats, stats_path = load_token_stats()
        stats_label = f"turn averages from {stats_path.name}" if stats_path else "no historical token stats"
        total_debater_cost, per_model_cost, total_judge_cost, per_judge_cost = estimate_cost(
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
                                judge_source_pool, main_cfg.num_judges, debate_seed, preview_usage, balanced_judges
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
                        judge_source_pool, main_cfg.num_judges, debate_seed, judge_usage, balanced_judges
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
                    judge_source_pool, main_cfg.num_judges, retry_seed, judge_usage, balanced_judges
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
