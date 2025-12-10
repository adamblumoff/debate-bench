"""Setup helpers for the `debatebench run` command."""
from __future__ import annotations

import random
import shutil
from datetime import datetime, timezone
from pathlib import Path

import typer

from ... import config as cfg
from ...settings import load_settings
from ..common import console
from .types import RunOptions, RunSetup


def _slugify_model_id(model_id: str) -> str:
    """Filesystem-friendly identifier for snapshot artifacts."""
    return model_id.replace("/", "-").replace(" ", "_")


def prepare_run(options: RunOptions) -> RunSetup:
    """Load configs/settings and establish run directories + snapshots."""
    (
        main_cfg,
        topics_cfg,
        config_debater_models,
        config_judge_models,
    ) = cfg.load_all_configs(
        options.config_path, options.topics_path, options.models_path, options.judges_path
    )

    incremental_mode = options.new_model_id is not None
    if incremental_mode and not options.run_tag:
        raise typer.BadParameter(
            "--new-model requires --run-tag pointing to an existing debates_<tag>.jsonl file."
        )
    run_tag = options.run_tag or datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
    debates_path = options.debates_path_arg.parent / f"debates_{run_tag}.jsonl"
    if incremental_mode and not debates_path.exists():
        raise typer.BadParameter(
            f"--new-model expects an existing debates file for run tag '{run_tag}' at {debates_path}."
        )

    run_dir = Path("results") / f"run_{run_tag}"
    viz_dir = Path("results") / f"viz_{run_tag}"
    plots_dir = Path("results") / f"plots_{run_tag}"
    ratings_path = Path("results") / f"ratings_{run_tag}.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = run_dir / "config_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    append_slug = _slugify_model_id(options.new_model_id) if incremental_mode and options.new_model_id else None
    cli_args_path = snapshot_dir / (
        "cli_args.json" if not incremental_mode else f"cli_args_append_{append_slug}.json"
    )
    selection_snapshot_path = snapshot_dir / (
        "effective_selection.json"
        if not incremental_mode
        else f"effective_selection_append_{append_slug}.json"
    )

    # Preserve input config files for reproducibility (avoid clobbering baseline when appending).
    for src in (options.config_path, options.topics_path, options.models_path, options.judges_path):
        try:
            dest = snapshot_dir / src.name
            if incremental_mode and dest.exists():
                continue
            shutil.copy(src, dest)
        except FileNotFoundError:
            pass

    if (not topics_cfg) and (not incremental_mode):
        raise typer.BadParameter("Topics list is empty.")

    rng = random.Random(options.seed)
    settings = load_settings()

    console.print(f"[cyan]Run tag:[/cyan] {run_tag}")

    return RunSetup(
        options=options,
        settings=settings,
        main_cfg=main_cfg,
        topics=topics_cfg,
        debater_models=config_debater_models,
        judge_models=config_judge_models,
        topics_selected=topics_cfg,
        run_tag=run_tag,
        debates_path=debates_path,
        run_dir=run_dir,
        viz_dir=viz_dir,
        plots_dir=plots_dir,
        ratings_path=ratings_path,
        snapshot_dir=snapshot_dir,
        cli_args_path=cli_args_path,
        selection_snapshot_path=selection_snapshot_path,
        incremental_mode=incremental_mode,
        append_slug=append_slug,
        base_cli_args={},
        existing_records=[],
        judge_output_max_tokens=options.openrouter_judge_max_tokens,
        rng=rng,
    )


__all__ = ["prepare_run"]
