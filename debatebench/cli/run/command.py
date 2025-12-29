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
from ..common import console


def _normalize_options(options: RunOptions) -> None:
    if options.side_policy:
        policy = options.side_policy.lower()
        if policy == "balanced":
            options.balanced_sides = True
            options.swap_sides = False
        elif policy == "random":
            options.balanced_sides = False
            options.swap_sides = True
        elif policy == "fixed":
            options.balanced_sides = False
            options.swap_sides = False
        else:
            raise typer.BadParameter("side_policy must be one of: balanced, random, fixed.")
    else:
        if options.swap_sides or not options.balanced_sides:
            console.print("[yellow]Deprecated:[/yellow] use --side-policy instead of --balanced-sides/--swap-sides.")
        if options.swap_sides and options.balanced_sides:
            console.print("[yellow]Note:[/yellow] --swap-sides is ignored when --balanced-sides is enabled.")

    if options.judge_policy:
        policy = options.judge_policy.lower()
        if policy == "balanced":
            options.balanced_judges = True
        elif policy == "random":
            options.balanced_judges = False
        else:
            raise typer.BadParameter("judge_policy must be one of: balanced, random.")
    else:
        if options.balanced_judges is False:
            console.print("[yellow]Deprecated:[/yellow] use --judge-policy instead of --random-judges.")

    if options.ui:
        mode = options.ui.lower()
        if mode == "wizard":
            options.tui_wizard = True
            options.topic_select = True
        elif mode == "prompts":
            options.tui_wizard = False
            options.topic_select = True
        elif mode == "none":
            options.tui_wizard = False
            options.topic_select = False
        else:
            raise typer.BadParameter("ui must be one of: wizard, prompts, none.")
    else:
        if options.tui_wizard is False or options.topic_select is False:
            console.print("[yellow]Deprecated:[/yellow] use --ui instead of --tui-wizard/--topic-select.")

    if options.stage_max_tokens is not None:
        if options.openrouter_max_tokens is not None and options.openrouter_max_tokens != options.stage_max_tokens:
            console.print("[yellow]Note:[/yellow] --stage-max-tokens overrides --openrouter-max-tokens.")
        options.openrouter_max_tokens = options.stage_max_tokens
        options.apply_stage_token_limits = True
    else:
        if options.apply_stage_token_limits and options.openrouter_max_tokens is None:
            console.print(
                "[yellow]Note:[/yellow] --apply-stage-token-limits ignored because --openrouter-max-tokens is not set."
            )
            options.apply_stage_token_limits = False


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
        Path("results/debates.jsonl"),
        help="Base path used to choose the output directory for debates_<run_tag>.jsonl.",
    ),
    run_tag: Optional[str] = typer.Option(
        None,
        help="Run tag for outputs (default: UTC timestamp run-YYYYMMDD-HHMMSS).",
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
    side_policy: str | None = typer.Option(
        None,
        "--side-policy",
        help="Side assignment policy: balanced, random, or fixed (replaces --balanced-sides/--swap-sides).",
        case_sensitive=False,
    ),
    balanced_judges: bool = typer.Option(
        True,
        "--balanced-judges/--random-judges",
        help="Balance judge usage across the run (default). Disable to sample judges uniformly at random.",
    ),
    judge_policy: str | None = typer.Option(
        None,
        "--judge-policy",
        help="Judge selection policy: balanced or random (replaces --balanced-judges/--random-judges).",
        case_sensitive=False,
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
        0.7,
        help="Temperature for OpenRouter-selected debaters (and quick-test config). Judges are forced to 0.0 in the adapter.",
    ),
    openrouter_max_tokens: Optional[int] = typer.Option(
        None,
        help="Debater token limit for OpenRouter-selected models. To cap debate turns, also pass --apply-stage-token-limits to apply this value to per-round token limits.",
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
    ui: str | None = typer.Option(
        None,
        "--ui",
        help="Selection UI: wizard, prompts, or none (replaces --tui-wizard/--topic-select).",
        case_sensitive=False,
    ),
    prod_run: bool = typer.Option(
        False,
        "--prod-run/--no-prod-run",
        help="Run using config files only (no interactive selection). Forces balanced judges and judges-from-selection.",
    ),
    apply_stage_token_limits: bool = typer.Option(
        False,
        help="Overwrite per-round token limits for opening/rebuttal/closing to --openrouter-max-tokens for this run.",
    ),
    stage_max_tokens: Optional[int] = typer.Option(
        None,
        "--stage-max-tokens",
        help="Explicit per-stage max tokens (replaces --apply-stage-token-limits + --openrouter-max-tokens).",
    ),
    skip_on_empty: bool = typer.Option(
        False,
        help="If a model returns empty content after retries, skip that model for the rest of the run instead of aborting all debates.",
    ),
    quick_test: bool = typer.Option(
        False,
        help="Run a quick test using configs/quick-test-models.yaml (1 random topic, fixed debaters/judges from that file).",
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
    postupload: bool = typer.Option(
        True,
        "--postupload/--no-postupload",
        help="After postrun, upload results to S3 using the upload-results command.",
    ),
    postupload_bucket: Optional[str] = typer.Option(
        None,
        help="S3 bucket for --postupload. Defaults from env (DEBATEBENCH_S3_BUCKET/S3_BUCKET) or 'debatebench-results'.",
    ),
    postupload_prefix: str = typer.Option(
        "",
        help="Key prefix inside the bucket for --postupload (omit leading slash). Defaults from env (DEBATEBENCH_S3_PREFIX/S3_PREFIX) or 'runs/<run_tag>'.",
    ),
    postupload_profile: Optional[str] = typer.Option(
        None,
        help="AWS profile name for --postupload. Defaults from env (DEBATEBENCH_AWS_PROFILE/AWS_PROFILE). Leave unset for Railway buckets.",
    ),
    postupload_region: Optional[str] = typer.Option(
        None,
        help="AWS region override for --postupload. Defaults from env (DEBATEBENCH_S3_REGION/S3_REGION).",
    ),
    postupload_include_artifacts: bool = typer.Option(
        False,
        help="When postuploading, also upload run_<tag>/, viz_<tag>/, plots_<tag>/, and ratings_<tag>.json if present.",
    ),
    postupload_dry_run: bool = typer.Option(
        False,
        help="List uploads for --postupload without sending to S3.",
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
        side_policy=side_policy,
        balanced_judges=balanced_judges,
        judge_policy=judge_policy,
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
        ui=ui,
        prod_run=prod_run,
        apply_stage_token_limits=apply_stage_token_limits,
        stage_max_tokens=stage_max_tokens,
        skip_on_empty=skip_on_empty,
        quick_test=quick_test,
        judges_test=judges_test,
        resume=resume,
        retry_failed=retry_failed,
        log_failed_judges=log_failed_judges,
        dry_run=dry_run,
        postrate=postrate,
        postupload=postupload,
        postupload_bucket=postupload_bucket,
        postupload_prefix=postupload_prefix,
        postupload_profile=postupload_profile,
        postupload_region=postupload_region,
        postupload_include_artifacts=postupload_include_artifacts,
        postupload_dry_run=postupload_dry_run,
        estimate_time=estimate_time,
    )

    _normalize_options(options)

    setup = prepare_run(options)
    selection_result = perform_selection(setup)
    plan_result = build_plan(selection_result.setup, selection_result.debates_per_pair)
    if plan_result.dry_run_only or plan_result.plan is None:
        return
    execute_plan(selection_result.setup, plan_result.plan)
    run_postrun(selection_result.setup)


__all__ = ["run_command"]
