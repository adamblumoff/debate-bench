"""Selection and configuration resolution for the `debatebench run` command."""
from __future__ import annotations

import json
import random
from typing import Optional

import typer

from ..common import console
from .selection_incremental import apply_incremental_selection, _infer_debates_per_pair
from .selection_quick import apply_judges_test_selection, apply_quick_test_selection
from .selection_standard import apply_standard_selection
from .selection_state import SelectionState
from .types import RunOptions, RunSetup

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
    rng = setup.rng if isinstance(setup.rng, random.Random) else random.Random(opts.seed)
    state = SelectionState(
        main_cfg=setup.main_cfg,
        topics=setup.topics,
        debater_models=setup.debater_models,
        judge_models=setup.judge_models,
        topics_selected=setup.topics_selected,
        debates_per_pair=opts.debates_per_pair,
        base_cli_args={},
        existing_records=[],
        judge_output_max_tokens=setup.judge_output_max_tokens,
        rng=rng,
    )

    # Incremental append path
    if setup.incremental_mode:
        if opts.quick_test or opts.judges_test:
            raise typer.BadParameter("--new-model cannot be combined with --quick-test or --judges-test.")
        state = apply_incremental_selection(state, setup)
    else:
        if opts.quick_test and opts.judges_test:
            raise typer.BadParameter("Choose only one of --quick-test or --judges-test.")

        if opts.quick_test:
            state = apply_quick_test_selection(state, setup)
        elif opts.judges_test:
            state = apply_judges_test_selection(state, setup)
        else:
            state = apply_standard_selection(state, setup)

    _clamp_num_judges(state.main_cfg, state.judge_models)

    if len(state.debater_models) < 2:
        raise typer.BadParameter("Need at least two debater models after selection.")

    if state.debates_per_pair is None:
        if setup.incremental_mode:
            raise typer.BadParameter(
                "Could not infer debates_per_pair from the existing run; please provide --debates-per-pair."
            )
        state.debates_per_pair = 1

    if opts.apply_stage_token_limits:
        _apply_stage_limits(state.main_cfg, opts.openrouter_max_tokens)

    cli_args = {
        "config_path": str(opts.config_path),
        "topics_path": str(opts.topics_path),
        "models_path": str(opts.models_path),
        "judges_path": str(opts.judges_path),
        "debates_path_arg": str(setup.debates_path),
        "run_tag": setup.run_tag,
        "new_model_id": opts.new_model_id,
        "sample_topics": opts.sample_topics,
        "debates_per_pair": state.debates_per_pair,
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
        "main_config": state.main_cfg.dict(),
        "topics_selected": [t.dict() for t in state.topics_selected],
        "debater_models": [m.dict() for m in state.debater_models],
        "judge_models": [j.dict() for j in state.judge_models],
    }
    with setup.selection_snapshot_path.open("w", encoding="utf-8") as f:
        json.dump(selection_snapshot, f, indent=2)

    setup.main_cfg = state.main_cfg
    setup.topics_selected = state.topics_selected
    setup.debater_models = state.debater_models
    setup.judge_models = state.judge_models
    setup.judge_output_max_tokens = state.judge_output_max_tokens
    setup.existing_records = state.existing_records
    setup.base_cli_args = state.base_cli_args

    return setup, state.debates_per_pair


__all__ = ["perform_selection", "_infer_debates_per_pair"]
