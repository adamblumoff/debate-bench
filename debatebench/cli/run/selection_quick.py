"""Quick-test and judges-test selection helpers."""
from __future__ import annotations

from pathlib import Path

import typer
import yaml

from ...schema import DebaterModelConfig, JudgeModelConfig
from ..common import console
from .selection_state import SelectionState

QUICK_TEST_CONFIG_PATH = Path("configs/quick-test-models.yaml")


def apply_quick_test_selection(state: SelectionState, setup) -> SelectionState:
    opts = setup.options
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
    opts.balanced_sides = False  # single orientation: pro=first model, con=second
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


__all__ = ["apply_quick_test_selection", "apply_judges_test_selection", "QUICK_TEST_CONFIG_PATH"]
