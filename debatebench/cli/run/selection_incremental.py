"""Incremental append selection logic for `debatebench run`."""
from __future__ import annotations

import json
from collections import Counter

import typer

from ... import config as cfg
from ...schema import DebateRecord, DebaterModelConfig, JudgeModelConfig
from ...storage import load_debate_records
from ..common import console
from .selection_state import SelectionState


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


def apply_incremental_selection(state: SelectionState, setup) -> SelectionState:
    opts = setup.options
    base_selection_file = setup.snapshot_dir / "effective_selection.json"
    base_cli_args_path = setup.snapshot_dir / "cli_args.json"
    if not base_selection_file.exists():
        raise typer.BadParameter(f"Base selection snapshot missing: {base_selection_file}.")
    if not base_cli_args_path.exists():
        raise typer.BadParameter(f"Base CLI snapshot missing: {base_cli_args_path}.")

    with base_selection_file.open("r", encoding="utf-8") as f:
        base_selection = json.load(f)
    with base_cli_args_path.open("r", encoding="utf-8") as f:
        state.base_cli_args = json.load(f)

    try:
        state.main_cfg = cfg.MainConfig(**base_selection["main_config"])
    except Exception as e:  # pylint: disable=broad-except
        raise typer.BadParameter(f"Failed to load main config from {base_selection_file}: {e}") from e

    state.topics_selected = [cfg.Topic(**t) for t in base_selection.get("topics_selected", [])]
    incumbent_models = [DebaterModelConfig(**m) for m in base_selection.get("debater_models", [])]
    state.judge_models = [JudgeModelConfig(**j) for j in base_selection.get("judge_models", [])]
    if not incumbent_models:
        raise typer.BadParameter(f"No debaters found in baseline snapshot {base_selection_file}.")

    state.existing_records = load_debate_records(setup.debates_path)
    if not state.existing_records:
        raise typer.BadParameter(
            f"Existing debates file {setup.debates_path} is empty; cannot infer prior schedule."
        )

    topics_in_log = []
    seen_topics = set()
    for rec in state.existing_records:
        t = rec.transcript.topic
        if t.id not in seen_topics:
            topics_in_log.append(cfg.Topic(**t.dict()))
            seen_topics.add(t.id)
    state.topics_selected = topics_in_log
    if not state.topics_selected:
        raise typer.BadParameter(f"No topics found in debates file {setup.debates_path}.")

    inferred_per_pair, anomalies = _infer_debates_per_pair(state.existing_records)
    base_cli_per_pair = state.base_cli_args.get("debates_per_pair")
    if state.debates_per_pair is None:
        state.debates_per_pair = base_cli_per_pair or inferred_per_pair or 1
    if base_cli_per_pair and inferred_per_pair and base_cli_per_pair != inferred_per_pair:
        console.print(
            f"[yellow]Planned debates_per_pair={base_cli_per_pair} but observed {inferred_per_pair} in log; using observed value.[/yellow]"
        )
        state.debates_per_pair = inferred_per_pair
    if anomalies:
        preview = list(anomalies.items())[:3]
        details = ", ".join(f"{k[1]} vs {k[2]} on {k[0]} -> {v}" for k, v in preview)
        console.print(
            f"[yellow]Uneven prior debate counts detected ({len(anomalies)} anomalies). "
            f"Continuing with existing counts; sample: {details}[/yellow]"
        )

    # Carry forward base CLI toggles to mirror baseline schedule semantics.
    opts.balanced_sides = state.base_cli_args.get("balanced_sides", opts.balanced_sides)
    opts.swap_sides = state.base_cli_args.get("swap_sides", opts.swap_sides)
    opts.balanced_judges = state.base_cli_args.get("balanced_judges", opts.balanced_judges)
    opts.judges_from_selection = state.base_cli_args.get("judges_from_selection", opts.judges_from_selection)
    opts.apply_stage_token_limits = state.base_cli_args.get("apply_stage_token_limits", opts.apply_stage_token_limits)
    opts.openrouter_max_tokens = state.base_cli_args.get("openrouter_max_tokens", opts.openrouter_max_tokens)
    opts.openrouter_judge_max_tokens = state.base_cli_args.get(
        "openrouter_judge_max_tokens", opts.openrouter_judge_max_tokens
    )
    state.judge_output_max_tokens = opts.openrouter_judge_max_tokens

    new_model_cfg = next((m for m in state.debater_models if m.id == opts.new_model_id), None)
    if new_model_cfg is None:
        raise typer.BadParameter(f"New model id '{opts.new_model_id}' not found in {opts.models_path}.")
    combined_models = []
    seen_ids = set()
    for m in incumbent_models + [new_model_cfg]:
        if m.id in seen_ids:
            continue
        seen_ids.add(m.id)
        combined_models.append(m)
    state.debater_models = combined_models

    existing_new = sum(
        1
        for rec in state.existing_records
        if rec.transcript.pro_model_id == opts.new_model_id
        or rec.transcript.con_model_id == opts.new_model_id
    )
    console.print(
        f"[cyan]Incremental mode:[/cyan] base run '{setup.run_tag}' with {len(state.topics_selected)} topics, "
        f"{len(incumbent_models)} incumbents; scheduling {state.debates_per_pair} debate(s) per ordered pair per topic for new model '{opts.new_model_id}'."
    )
    if existing_new:
        console.print(
            f"[yellow]Detected {existing_new} existing debates with {opts.new_model_id}; counts will be reused so only missing matchups are scheduled.[/yellow]"
        )

    return state


__all__ = ["apply_incremental_selection", "_infer_debates_per_pair"]
