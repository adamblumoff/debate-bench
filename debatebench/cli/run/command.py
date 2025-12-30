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
    if options.side_policy is None:
        raise typer.BadParameter("side_policy must be one of: balanced, random, fixed.")
    if options.judge_policy is None:
        raise typer.BadParameter("judge_policy must be one of: balanced, random.")
    if options.ui is None:
        raise typer.BadParameter("ui must be one of: wizard, prompts, none.")

    options.side_policy = options.side_policy.lower()
    options.judge_policy = options.judge_policy.lower()
    options.ui = options.ui.lower()

    if options.side_policy not in {"balanced", "random", "fixed"}:
        raise typer.BadParameter("side_policy must be one of: balanced, random, fixed.")
    if options.judge_policy not in {"balanced", "random"}:
        raise typer.BadParameter("judge_policy must be one of: balanced, random.")
    if options.ui not in {"wizard", "prompts", "none"}:
        raise typer.BadParameter("ui must be one of: wizard, prompts, none.")

    if options.ui == "none":
        options.openrouter_select = False

    if options.stage_max_tokens is not None:
        if options.openrouter_max_tokens is not None and options.openrouter_max_tokens != options.stage_max_tokens:
            console.print("[yellow]Note:[/yellow] --stage-max-tokens overrides --openrouter-max-tokens.")
        options.openrouter_max_tokens = options.stage_max_tokens


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
    side_policy: str | None = typer.Option(
        "balanced",
        "--side-policy",
        help="Side assignment policy: balanced, random, or fixed.",
        case_sensitive=False,
    ),
    dual_round_order: bool = typer.Option(
        False,
        "--dual-round-order/--no-dual-round-order",
        help="Run both pro-first and con-first round orders back-to-back and append to the same debates file.",
    ),
    judge_policy: str | None = typer.Option(
        "balanced",
        "--judge-policy",
        help="Judge selection policy: balanced or random.",
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
        help="Debater token limit for OpenRouter-selected models. To cap debate turns, use --stage-max-tokens.",
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
    ui: str | None = typer.Option(
        "wizard",
        "--ui",
        help="Selection UI: wizard, prompts, or none.",
        case_sensitive=False,
    ),
    prod_run: bool = typer.Option(
        False,
        "--prod-run/--no-prod-run",
        help="Run using config files only (no interactive selection). Forces balanced judges and judges-from-selection.",
    ),
    stage_max_tokens: Optional[int] = typer.Option(
        None,
        "--stage-max-tokens",
        help="Explicit per-stage max tokens.",
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
        side_policy=side_policy,
        dual_round_order=dual_round_order,
        judge_policy=judge_policy,
        openrouter_select=openrouter_select,
        openrouter_months=openrouter_months,
        openrouter_temperature=openrouter_temperature,
        openrouter_max_tokens=openrouter_max_tokens,
        openrouter_probe=openrouter_probe,
        judges_from_selection=judges_from_selection,
        openrouter_judge_months=openrouter_judge_months,
        openrouter_judge_max_tokens=openrouter_judge_max_tokens,
        ui=ui,
        prod_run=prod_run,
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
    if options.dual_round_order:
        from .round_order import flip_round_speakers, infer_round_order_from_rounds

        base_cfg = selection_result.setup.main_cfg
        base_order = infer_round_order_from_rounds(base_cfg.rounds)
        alt_order = "con-first" if base_order == "pro-first" else "pro-first"
        alt_cfg = base_cfg.model_copy(update={"rounds": flip_round_speakers(base_cfg.rounds)})

        round_variants = [
            (base_order, base_cfg),
            (alt_order, alt_cfg),
        ]
        for label, cfg in round_variants:
            selection_result.setup.main_cfg = cfg
            plan_result = build_plan(
                selection_result.setup,
                selection_result.debates_per_pair,
                schedule_label=label,
            )
            if plan_result.dry_run_only or plan_result.plan is None:
                continue
            execution_result = execute_plan(selection_result.setup, plan_result.plan)
            if execution_result.failed_total > 0:
                console.print(
                    f"[yellow]Run finished with {execution_result.failed_total} failed debates "
                    f"(and {execution_result.skipped_total} skipped) for {label}.[/yellow]"
                )
            if execution_result.banned_models:
                console.print(
                    f"[yellow]Banned models during run ({label}): "
                    f"{', '.join(execution_result.banned_models)}[/yellow]"
                )
        if options.dry_run:
            return
        run_postrun(selection_result.setup)
        return

    plan_result = build_plan(selection_result.setup, selection_result.debates_per_pair)
    if plan_result.dry_run_only or plan_result.plan is None:
        return
    execute_plan(selection_result.setup, plan_result.plan)
    run_postrun(selection_result.setup)


__all__ = ["run_command"]
