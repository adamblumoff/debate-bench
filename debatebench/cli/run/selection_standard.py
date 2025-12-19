"""Standard selection flow for `debatebench run`."""
from __future__ import annotations

import typer

from ...openrouter import fetch_recent_openrouter_models, probe_model
from ...schema import DebaterModelConfig, JudgeModelConfig
from ..common import console
from .selection import (
    SelectionCancelled,
    _interactive_select_models,
    _interactive_select_topics,
    selection_wizard,
)
from .selection_state import SelectionState


def apply_standard_selection(state: SelectionState, setup) -> SelectionState:
    opts = setup.options
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
                topics=state.topics if opts.topic_select else [],
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
            state.topics_selected, debater_entries, judge_entries = wizard_result
            if not state.topics_selected:
                raise typer.BadParameter("All topics were disabled; nothing to run.")
            state.debater_models = []
            for entry in debater_entries:
                model_id = entry["id"]
                state.debater_models.append(
                    DebaterModelConfig(
                        id=model_id.replace("/", "-"),
                        provider="openrouter",
                        model=model_id,
                        token_limit=opts.openrouter_max_tokens,
                        endpoint=None,
                        parameters={"temperature": opts.openrouter_temperature},
                    )
                )
            if not state.debater_models:
                raise typer.BadParameter("All models were disabled; nothing to run.")
            if opts.judges_from_selection:
                state.judge_models = state.debater_models
            else:
                state.judge_models = []
                for entry in judge_entries:
                    model_id = entry["id"]
                    state.judge_models.append(
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
                if not state.judge_models:
                    raise typer.BadParameter("All judge models were disabled; nothing to run.")
            if opts.sample_topics is not None:
                if opts.sample_topics <= 0:
                    raise typer.BadParameter("sample_topics must be positive.")
                state.topics_selected = state.rng.sample(
                    state.topics_selected, k=min(opts.sample_topics, len(state.topics_selected))
                )

    if not used_wizard:
        state.topics_selected = state.topics
        if opts.topic_select:
            state.topics_selected = _interactive_select_topics(state.topics, console)
            if not state.topics_selected:
                raise typer.BadParameter("All topics were disabled; nothing to run.")
        if opts.sample_topics is not None:
            if opts.sample_topics <= 0:
                raise typer.BadParameter("sample_topics must be positive.")
            state.topics_selected = state.rng.sample(
                state.topics_selected, k=min(opts.sample_topics, len(state.topics_selected))
            )

        if opts.openrouter_select:
            selected_entries = _interactive_select_models(
                debater_catalog, console, title="Select Debater Models"
            )
            if not selected_entries:
                raise typer.BadParameter("All models were disabled; nothing to run.")

            state.debater_models = []
            for entry in selected_entries:
                model_id = entry["id"]
                state.debater_models.append(
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
                f"[green]Selected {len(state.debater_models)} debater models from OpenRouter (last {opts.openrouter_months} month(s)).[/green]"
            )

        if opts.openrouter_probe and state.debater_models:
            console.print("[cyan]Probing selected models with 1-token requests...[/cyan]")
            usable = []
            dropped = []
            for m in state.debater_models:
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
            state.debater_models = usable
            if len(state.debater_models) < 2:
                raise typer.BadParameter("Fewer than two usable models after probe; aborting.")

        if opts.judges_from_selection:
            state.judge_models = state.debater_models
            state.main_cfg.num_judges = min(max(state.main_cfg.num_judges, 2), len(state.judge_models))
            if len(state.judge_models) < 2:
                raise typer.BadParameter("Need at least two judges after selection.")
        else:
            selected_judges = _interactive_select_models(
                judge_catalog, console, title="Select Judge Models"
            )
            if not selected_judges:
                raise typer.BadParameter("All judge models were disabled; nothing to run.")
            state.judge_models = []
            for entry in selected_judges:
                model_id = entry["id"]
                state.judge_models.append(
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
            if opts.openrouter_probe and state.judge_models:
                console.print("[cyan]Probing selected judge models with 1-token requests...[/cyan]")
                usable_j = []
                dropped_j = []
                for j in state.judge_models:
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
                state.judge_models = usable_j

    return state


__all__ = ["apply_standard_selection"]
