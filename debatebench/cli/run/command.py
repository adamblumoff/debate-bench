"""Run command orchestrator for DebateBench."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .executor import execute_plan
from .planner import build_plan
from .postrun import run_postrun
from .selection_flow import perform_selection
from .setup import prepare_run
from .types import RunOptions


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
    options = RunOptions(
        config_path=config_path,
        topics_path=topics_path,
        models_path=models_path,
        judges_path=judges_path,
        debates_path_arg=debates_path,
        run_tag=run_tag,
        new_model_id=new_model_id,
        sample_topics=sample_topics,
        debates_per_pair=debates_per_pair,
        seed=seed if seed is not None else 12345,
        swap_sides=swap_sides,
        balanced_sides=balanced_sides,
        balanced_judges=balanced_judges,
        openrouter_select=openrouter_select,
        openrouter_months=openrouter_months,
        openrouter_temperature=openrouter_temperature,
        openrouter_max_tokens=openrouter_max_tokens,
        openrouter_probe=openrouter_probe,
        judges_from_selection=judges_from_selection,
        openrouter_judge_months=openrouter_judge_months,
        openrouter_judge_max_tokens=openrouter_judge_max_tokens,
        topic_select=topic_select,
        tui_wizard=tui_wizard,
        apply_stage_token_limits=apply_stage_token_limits,
        skip_on_empty=skip_on_empty,
        quick_test=quick_test,
        judges_test=judges_test,
        resume=resume,
        retry_failed=retry_failed,
        log_failed_judges=log_failed_judges,
        dry_run=dry_run,
        postrate=postrate,
        estimate_time=estimate_time,
    )

    setup = prepare_run(options)
    setup, final_debates_per_pair = perform_selection(setup)
    plan, dry_run_only = build_plan(setup, final_debates_per_pair)
    if dry_run_only or plan is None:
        return
    execute_plan(setup, plan)
    run_postrun(setup)


__all__ = ["run_command"]
