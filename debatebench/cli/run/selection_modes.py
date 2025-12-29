"""Selection helpers for quick-test, judges-test, and incremental modes."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import typer
import yaml

from ... import config as cfg
from ...schema import DebateRecord, DebaterModelConfig, JudgeModelConfig
from ...storage import load_debate_records
from ..common import console
from .selection_state import SelectionState

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
    base_side_policy = state.base_cli_args.get("side_policy")
    if base_side_policy:
        opts.side_policy = base_side_policy
    else:
        balanced_sides = state.base_cli_args.get("balanced_sides")
        swap_sides = state.base_cli_args.get("swap_sides")
        if balanced_sides:
            opts.side_policy = "balanced"
        elif swap_sides:
            opts.side_policy = "random"
        else:
            opts.side_policy = "fixed"

    base_judge_policy = state.base_cli_args.get("judge_policy")
    if base_judge_policy:
        opts.judge_policy = base_judge_policy
    else:
        balanced_judges = state.base_cli_args.get("balanced_judges")
        opts.judge_policy = "balanced" if balanced_judges else "random"

    opts.judges_from_selection = state.base_cli_args.get("judges_from_selection", opts.judges_from_selection)
    opts.openrouter_max_tokens = state.base_cli_args.get("openrouter_max_tokens", opts.openrouter_max_tokens)
    opts.openrouter_judge_max_tokens = state.base_cli_args.get(
        "openrouter_judge_max_tokens", opts.openrouter_judge_max_tokens
    )

    base_ui = state.base_cli_args.get("ui")
    if base_ui:
        opts.ui = base_ui
    else:
        tui_wizard = state.base_cli_args.get("tui_wizard")
        topic_select = state.base_cli_args.get("topic_select")
        if tui_wizard:
            opts.ui = "wizard"
        elif topic_select:
            opts.ui = "prompts"
        else:
            opts.ui = "none"

    base_stage_max = state.base_cli_args.get("stage_max_tokens")
    if base_stage_max is not None:
        opts.stage_max_tokens = base_stage_max
    else:
        apply_stage = state.base_cli_args.get("apply_stage_token_limits")
        if apply_stage:
            opts.stage_max_tokens = opts.openrouter_max_tokens
    if opts.stage_max_tokens is not None and opts.openrouter_max_tokens is None:
        opts.openrouter_max_tokens = opts.stage_max_tokens

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


def apply_quick_test_selection(state: SelectionState, setup) -> SelectionState:
    opts = setup.options
    opts.postupload = False
    opts.postupload_include_artifacts = False
    if opts.sample_topics is not None:
        sample_count = max(1, min(len(state.topics), opts.sample_topics))
        state.topics_selected = state.rng.sample(state.topics, sample_count)
    else:
        state.topics_selected = [state.rng.choice(state.topics)]
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

    state.debater_models = []
    for entry in debaters_cfg:
        params = dict(entry.get("parameters") or {})
        if opts.openrouter_temperature is not None:
            params["temperature"] = opts.openrouter_temperature
        token_limit = opts.openrouter_max_tokens if opts.openrouter_max_tokens is not None else entry.get("token_limit")
        state.debater_models.append(
            DebaterModelConfig(
                id=entry["id"],
                provider=entry.get("provider", "openrouter"),
                model=entry["model"],
                token_limit=token_limit,
                endpoint=entry.get("endpoint"),
                parameters=params,
            )
        )

    state.judge_models = []
    for entry in judges_cfg:
        params = dict(entry.get("parameters") or {})
        if opts.openrouter_temperature is not None:
            params["temperature"] = opts.openrouter_temperature
        token_limit = state.judge_output_max_tokens if state.judge_output_max_tokens is not None else entry.get("token_limit")
        state.judge_models.append(
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
        state.main_cfg.num_judges = configured_num_judges
    state.main_cfg.num_judges = state.main_cfg.num_judges or len(state.judge_models) or 3
    if opts.sample_topics is not None:
        console.print(
            f"[cyan]Quick test mode: {len(state.topics_selected)} random topic(s) using models from {QUICK_TEST_CONFIG_PATH}.[/cyan]"
        )
    else:
        console.print(
            f"[cyan]Quick test mode: 1 random topic using models from {QUICK_TEST_CONFIG_PATH}.[/cyan]"
        )
    return state


def apply_judges_test_selection(state: SelectionState, setup) -> SelectionState:
    opts = setup.options
    state.topics_selected = [state.rng.choice(state.topics)]
    opts.side_policy = "fixed"  # single orientation: pro=first model, con=second
    state.debates_per_pair = 1
    state.debater_models = [
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
    state.judge_models = [
        JudgeModelConfig(
            id="google-gemini-3-pro-preview",
            provider="openrouter",
            model="google/gemini-3-pro-preview",
            token_limit=state.judge_output_max_tokens,
            endpoint=None,
            prompt_style=None,
            parameters={"temperature": 0.0},
        ),
        JudgeModelConfig(
            id="openai-gpt-5.1",
            provider="openrouter",
            model="openai/gpt-5.1",
            token_limit=state.judge_output_max_tokens,
            endpoint=None,
            prompt_style=None,
            parameters={"temperature": 0.0},
        ),
    ]
    state.main_cfg.num_judges = 2
    console.print(
        "[cyan]Judges test mode: 1 random topic, Claude Haiku 4.5 vs Gemini 2.5 Flash Lite; judges Gemini 3 Pro + OpenAI GPT-5.1.[/cyan]"
    )
    return state


__all__ = [
    "apply_incremental_selection",
    "apply_quick_test_selection",
    "apply_judges_test_selection",
    "_infer_debates_per_pair",
    "QUICK_TEST_CONFIG_PATH",
]
