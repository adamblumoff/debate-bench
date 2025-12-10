"""Selection and configuration resolution for the `debatebench run` command."""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Optional

import typer
import yaml

from ... import config as cfg
from ...openrouter import fetch_recent_openrouter_models, probe_model
from ...schema import DebateRecord, DebaterModelConfig, JudgeModelConfig
from ...storage import load_debate_records
from ..common import console
from .selection import (
    SelectionCancelled,
    _fallback_select_models,
    _fallback_select_topics,
    _interactive_select_models,
    _interactive_select_topics,
    selection_wizard,
)
from .types import RunOptions, RunSetup

QUICK_TEST_CONFIG_PATH = Path("configs/quick-test-models.yaml")


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
    common_count, _ = Counter(counts.values()).most_common(1)[0]
    anomalies = {k: v for k, v in counts.items() if v != common_count}
    return common_count, anomalies


def _clamp_num_judges(main_cfg, judge_models):
    main_cfg.num_judges = min(max(main_cfg.num_judges, 2), len(judge_models))
    if len(judge_models) < main_cfg.num_judges:
        main_cfg.num_judges = len(judge_models)
    if main_cfg.num_judges < 2:
        raise typer.BadParameter("Need at least two judges in the final pool.")


def _apply_stage_limits(main_cfg, max_tokens: Optional[int]):
    stage_limits = {"opening": max_tokens, "rebuttal": max_tokens, "closing": max_tokens}
    new_rounds = []
    for r in main_cfg.rounds:
        lim = stage_limits.get(r.stage, r.token_limit)
        new_rounds.append(r.copy(update={"token_limit": lim}))
    main_cfg.rounds = new_rounds


def perform_selection(setup: RunSetup) -> tuple[RunSetup, int]:
    """Resolve models/topics, handle quick/incremental modes, and persist snapshots."""
    opts: RunOptions = setup.options
    main_cfg = setup.main_cfg
    topics = setup.topics
    debater_models = setup.debater_models
    judge_models = setup.judge_models
    topics_selected = setup.topics_selected
    judge_output_max_tokens = setup.judge_output_max_tokens
    rng = setup.rng if isinstance(setup.rng, random.Random) else random.Random(opts.seed)

    debates_per_pair = opts.debates_per_pair
    base_cli_args = {}
    existing_records: list[DebateRecord] = []

    # Incremental append path
    if setup.incremental_mode:
        if opts.quick_test or opts.judges_test:
            raise typer.BadParameter("--new-model cannot be combined with --quick-test or --judges-test.")
        base_selection_file = setup.snapshot_dir / "effective_selection.json"
        base_cli_args_path = setup.snapshot_dir / "cli_args.json"
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

        existing_records = load_debate_records(setup.debates_path)
        if not existing_records:
            raise typer.BadParameter(f"Existing debates file {setup.debates_path} is empty; cannot infer prior schedule.")
        topics_in_log = []
        seen_topics = set()
        for rec in existing_records:
            t = rec.transcript.topic
            if t.id not in seen_topics:
                topics_in_log.append(cfg.Topic(**t.dict()))
                seen_topics.add(t.id)
        topics_selected = topics_in_log
        if not topics_selected:
            raise typer.BadParameter(f"No topics found in debates file {setup.debates_path}.")
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
            preview = list(anomalies.items())[:3]
            details = ", ".join(f"{k[1]} vs {k[2]} on {k[0]} -> {v}" for k, v in preview)
            console.print(
                f"[yellow]Uneven prior debate counts detected ({len(anomalies)} anomalies). "
                f"Continuing with existing counts; sample: {details}[/yellow]"
            )

        # Carry forward base CLI toggles to mirror baseline schedule semantics.
        opts.balanced_sides = base_cli_args.get("balanced_sides", opts.balanced_sides)
        opts.swap_sides = base_cli_args.get("swap_sides", opts.swap_sides)
        opts.balanced_judges = base_cli_args.get("balanced_judges", opts.balanced_judges)
        opts.judges_from_selection = base_cli_args.get("judges_from_selection", opts.judges_from_selection)
        opts.apply_stage_token_limits = base_cli_args.get("apply_stage_token_limits", opts.apply_stage_token_limits)
        opts.openrouter_max_tokens = base_cli_args.get("openrouter_max_tokens", opts.openrouter_max_tokens)
        opts.openrouter_judge_max_tokens = base_cli_args.get(
            "openrouter_judge_max_tokens", opts.openrouter_judge_max_tokens
        )
        judge_output_max_tokens = opts.openrouter_judge_max_tokens

        new_model_cfg = next((m for m in setup.debater_models if m.id == opts.new_model_id), None)
        if new_model_cfg is None:
            raise typer.BadParameter(f"New model id '{opts.new_model_id}' not found in {opts.models_path}.")
        combined_models = []
        seen_ids = set()
        for m in incumbent_models + [new_model_cfg]:
            if m.id in seen_ids:
                continue
            seen_ids.add(m.id)
            combined_models.append(m)
        debater_models = combined_models
        existing_new = sum(
            1
            for rec in existing_records
            if rec.transcript.pro_model_id == opts.new_model_id or rec.transcript.con_model_id == opts.new_model_id
        )
        console.print(
            f"[cyan]Incremental mode:[/cyan] base run '{setup.run_tag}' with {len(topics_selected)} topics, "
            f"{len(incumbent_models)} incumbents; scheduling {debates_per_pair} debate(s) per ordered pair per topic for new model '{opts.new_model_id}'."
        )
        if existing_new:
            console.print(
                f"[yellow]Detected {existing_new} existing debates with {opts.new_model_id}; counts will be reused so only missing matchups are scheduled.[/yellow]"
            )
    else:
        if opts.quick_test and opts.judges_test:
            raise typer.BadParameter("Choose only one of --quick-test or --judges-test.")

        if opts.quick_test:
            topics_selected = [rng.choice(topics)]
            try:
                quick_test_cfg = yaml.safe_load(QUICK_TEST_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            except FileNotFoundError as e:  # pragma: no cover - config is expected to exist
                raise typer.BadParameter(f"Quick test config missing: {QUICK_TEST_CONFIG_PATH}") from e

            debaters_cfg = quick_test_cfg.get("debaters") or quick_test_cfg.get("models") or []
            judges_cfg = quick_test_cfg.get("judges") or []
            if not isinstance(debaters_cfg, list) or not debaters_cfg:
                raise typer.BadParameter(f"No debaters found in quick test config {QUICK_TEST_CONFIG_PATH}.")
            if not isinstance(judges_cfg, list) or not judges_cfg:
                raise typer.BadParameter(f"No judges found in quick test config {QUICK_TEST_CONFIG_PATH}.")

            debater_models = []
            for entry in debaters_cfg:
                params = dict(entry.get("parameters") or {})
                if opts.openrouter_temperature is not None:
                    params["temperature"] = opts.openrouter_temperature
                token_limit = opts.openrouter_max_tokens if opts.openrouter_max_tokens is not None else entry.get("token_limit")
                debater_models.append(
                    DebaterModelConfig(
                        id=entry["id"],
                        provider=entry.get("provider", "openrouter"),
                        model=entry["model"],
                        token_limit=token_limit,
                        endpoint=entry.get("endpoint"),
                        parameters=params,
                    )
                )

            judge_models = []
            for entry in judges_cfg:
                params = dict(entry.get("parameters") or {})
                if opts.openrouter_temperature is not None:
                    params["temperature"] = opts.openrouter_temperature
                token_limit = judge_output_max_tokens if judge_output_max_tokens is not None else entry.get("token_limit")
                judge_models.append(
                    JudgeModelConfig(
                        id=entry["id"],
                        provider=entry.get("provider", "openrouter"),
                        model=entry["model"],
                        token_limit=token_limit,
                        endpoint=entry.get("endpoint"),
                        prompt_style=entry.get("prompt_style"),
                        parameters=params,
                    )
                )

            configured_num_judges = quick_test_cfg.get("num_judges")
            if configured_num_judges is not None:
                main_cfg.num_judges = configured_num_judges
            main_cfg.num_judges = main_cfg.num_judges or len(judge_models) or 3
            console.print(
                f"[cyan]Quick test mode: 1 random topic using models from {QUICK_TEST_CONFIG_PATH}.[/cyan]"
            )
        elif opts.judges_test:
            topics_selected = [rng.choice(topics)]
            opts.balanced_sides = False  # single orientation: pro=first model, con=second
            debates_per_pair = 1
            debater_models = [
                DebaterModelConfig(
                    id="anthropic-claude-haiku-4.5",
                    provider="openrouter",
                    model="anthropic/claude-haiku-4.5",
                    token_limit=opts.openrouter_max_tokens,
                    endpoint=None,
                    parameters={"temperature": 0.35},
                ),
                DebaterModelConfig(
                    id="google-gemini-2.5-flash-lite-preview-09-2025",
                    provider="openrouter",
                    model="google/gemini-2.5-flash-lite-preview-09-2025",
                    token_limit=opts.openrouter_max_tokens,
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
            console.print(
                "[cyan]Judges test mode: 1 random topic, Claude Haiku 4.5 vs Gemini 2.5 Flash Lite; judges Gemini 3 Pro + OpenAI GPT-5.1.[/cyan]"
            )
        else:
            debater_catalog = None
            if opts.openrouter_select:
                if not setup.settings.openrouter_api_key:
                    raise typer.BadParameter("OPENROUTER_API_KEY is required for interactive OpenRouter selection.")
                console.print(
                    f"[cyan]Fetching OpenRouter models from the last {opts.openrouter_months} month(s)...[/cyan]"
                )
                debater_catalog = fetch_recent_openrouter_models(
                    months=opts.openrouter_months,
                    api_key=setup.settings.openrouter_api_key,
                    site_url=setup.settings.openrouter_site_url,
                    site_name=setup.settings.openrouter_site_name,
                )
                if not debater_catalog:
                    raise typer.BadParameter(
                        f"No text-based OpenRouter models found in the last {opts.openrouter_months} month(s)."
                    )

            judge_catalog = None
            months_j = opts.openrouter_judge_months or opts.openrouter_months
            if not opts.judges_from_selection:
                console.print(
                    f"[cyan]Fetching OpenRouter judge candidates from the last {months_j} month(s)...[/cyan]"
                )
                judge_catalog = fetch_recent_openrouter_models(
                    months=months_j,
                    api_key=setup.settings.openrouter_api_key,
                    site_url=setup.settings.openrouter_site_url,
                    site_name=setup.settings.openrouter_site_name,
                )
                if not judge_catalog:
                    raise typer.BadParameter(
                        f"No text-based OpenRouter models found in the last {months_j} month(s) for judges."
                    )

            used_wizard = False
            if opts.tui_wizard:
                try:
                    wizard_result = selection_wizard(
                        topics=topics if opts.topic_select else [],
                        model_catalog=debater_catalog if opts.openrouter_select else [],
                        judge_catalog=judge_catalog if (not opts.judges_from_selection) else [],
                        enable_topics=opts.topic_select,
                        enable_models=opts.openrouter_select,
                        enable_judges=not opts.judges_from_selection,
                    )
                except SelectionCancelled:
                    console.print("[yellow]Selection cancelled.[/yellow]")
                    raise typer.Exit(code=1)
                if wizard_result is not None:
                    used_wizard = True
                    topics_selected, debater_entries, judge_entries = wizard_result
                    if not topics_selected:
                        raise typer.BadParameter("All topics were disabled; nothing to run.")
                    debater_models = []
                    for entry in debater_entries:
                        model_id = entry["id"]
                        debater_models.append(
                            DebaterModelConfig(
                                id=model_id.replace("/", "-"),
                                provider="openrouter",
                                model=model_id,
                                token_limit=opts.openrouter_max_tokens,
                                endpoint=None,
                                parameters={"temperature": opts.openrouter_temperature},
                            )
                        )
                    if not debater_models:
                        raise typer.BadParameter("All models were disabled; nothing to run.")
                    if opts.judges_from_selection:
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
                                    token_limit=opts.openrouter_judge_max_tokens,
                                    endpoint=None,
                                    prompt_style=None,
                                    parameters={"temperature": opts.openrouter_temperature},
                                )
                            )
                        if not judge_models:
                            raise typer.BadParameter("All judge models were disabled; nothing to run.")
                    if opts.sample_topics is not None:
                        if opts.sample_topics <= 0:
                            raise typer.BadParameter("sample_topics must be positive.")
                        topics_selected = rng.sample(topics_selected, k=min(opts.sample_topics, len(topics_selected)))

            if not opts.quick_test and not used_wizard:
                topics_selected = topics
                if opts.topic_select:
                    topics_selected = _interactive_select_topics(topics, console)
                    if not topics_selected:
                        raise typer.BadParameter("All topics were disabled; nothing to run.")
                if opts.sample_topics is not None:
                    if opts.sample_topics <= 0:
                        raise typer.BadParameter("sample_topics must be positive.")
                    topics_selected = rng.sample(topics_selected, k=min(opts.sample_topics, len(topics_selected)))

                if opts.openrouter_select:
                    selected_entries = _interactive_select_models(
                        debater_catalog, console, title="Select Debater Models"
                    )
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
                                token_limit=opts.openrouter_max_tokens,
                                endpoint=None,
                                parameters={"temperature": opts.openrouter_temperature},
                            )
                        )
                    console.print(
                        f"[green]Selected {len(debater_models)} debater models from OpenRouter (last {opts.openrouter_months} month(s)).[/green]"
                    )

                if opts.openrouter_probe and debater_models:
                    console.print("[cyan]Probing selected models with 1-token requests...[/cyan]")
                    usable = []
                    dropped = []
                    for m in debater_models:
                        err = probe_model(
                            model_id=m.model,
                            api_key=setup.settings.openrouter_api_key,
                            site_url=setup.settings.openrouter_site_url,
                            site_name=setup.settings.openrouter_site_name,
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

                if opts.judges_from_selection:
                    judge_models = debater_models
                    main_cfg.num_judges = min(max(main_cfg.num_judges, 2), len(judge_models))
                    if len(judge_models) < 2:
                        raise typer.BadParameter("Need at least two judges after selection.")
                else:
                    selected_judges = _interactive_select_models(
                        judge_catalog, console, title="Select Judge Models"
                    )
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
                                token_limit=opts.openrouter_judge_max_tokens,
                                endpoint=None,
                                prompt_style=None,
                                parameters={"temperature": opts.openrouter_temperature},
                            )
                        )
                    if opts.openrouter_probe and judge_models:
                        console.print("[cyan]Probing selected judge models with 1-token requests...[/cyan]")
                        usable_j = []
                        dropped_j = []
                        for j in judge_models:
                            err = probe_model(
                                model_id=j.model,
                                api_key=setup.settings.openrouter_api_key,
                                site_url=setup.settings.openrouter_site_url,
                                site_name=setup.settings.openrouter_site_name,
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

    _clamp_num_judges(main_cfg, judge_models)

    if len(debater_models) < 2:
        raise typer.BadParameter("Need at least two debater models after selection.")

    if debates_per_pair is None:
        if setup.incremental_mode:
            raise typer.BadParameter(
                "Could not infer debates_per_pair from the existing run; please provide --debates-per-pair."
            )
        debates_per_pair = 1

    if opts.apply_stage_token_limits:
        _apply_stage_limits(main_cfg, opts.openrouter_max_tokens)

    cli_args = {
        "config_path": str(opts.config_path),
        "topics_path": str(opts.topics_path),
        "models_path": str(opts.models_path),
        "judges_path": str(opts.judges_path),
        "debates_path_arg": str(setup.debates_path),
        "run_tag": setup.run_tag,
        "new_model_id": opts.new_model_id,
        "sample_topics": opts.sample_topics,
        "debates_per_pair": debates_per_pair,
        "seed": opts.seed,
        "swap_sides": opts.swap_sides,
        "balanced_sides": opts.balanced_sides,
        "balanced_judges": opts.balanced_judges,
        "openrouter_select": opts.openrouter_select,
        "openrouter_months": opts.openrouter_months,
        "openrouter_temperature": opts.openrouter_temperature,
        "openrouter_max_tokens": opts.openrouter_max_tokens,
        "openrouter_probe": opts.openrouter_probe,
        "judges_from_selection": opts.judges_from_selection,
        "openrouter_judge_months": opts.openrouter_judge_months,
        "openrouter_judge_max_tokens": opts.openrouter_judge_max_tokens,
        "topic_select": opts.topic_select,
        "tui_wizard": opts.tui_wizard,
        "apply_stage_token_limits": opts.apply_stage_token_limits,
        "skip_on_empty": opts.skip_on_empty,
        "quick_test": opts.quick_test,
        "judges_test": opts.judges_test,
        "resume": opts.resume,
        "retry_failed": opts.retry_failed,
        "dry_run": opts.dry_run,
        "postrate": opts.postrate,
    }
    with setup.cli_args_path.open("w", encoding="utf-8") as f:
        json.dump(cli_args, f, indent=2)

    selection_snapshot = {
        "main_config": main_cfg.dict(),
        "topics_selected": [t.dict() for t in topics_selected],
        "debater_models": [m.dict() for m in debater_models],
        "judge_models": [j.dict() for j in judge_models],
    }
    with setup.selection_snapshot_path.open("w", encoding="utf-8") as f:
        json.dump(selection_snapshot, f, indent=2)

    setup.main_cfg = main_cfg
    setup.topics_selected = topics_selected
    setup.debater_models = debater_models
    setup.judge_models = judge_models
    setup.judge_output_max_tokens = judge_output_max_tokens
    setup.existing_records = existing_records
    setup.base_cli_args = base_cli_args

    return setup, debates_per_pair


__all__ = ["perform_selection", "_infer_debates_per_pair"]
