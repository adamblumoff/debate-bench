"""Shared dataclasses for the `debatebench run` command."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...schema import DebateRecord, DebaterModelConfig, JudgeModelConfig

# Imported at runtime (not just TYPE_CHECKING) to keep simple typing downstream.
from ... import config as cfg  # noqa: WPS433
from ...settings import Settings  # noqa: WPS433


@dataclass
class RunOptions:
    """All CLI-supplied knobs for `debatebench run`."""

    config_path: Path
    topics_path: Path
    models_path: Path
    judges_path: Path
    debates_path_arg: Path
    run_tag: Optional[str]
    new_model_id: Optional[str]
    sample_topics: Optional[int]
    debates_per_pair: Optional[int]
    seed: Optional[int]
    swap_sides: bool
    balanced_sides: bool
    balanced_judges: bool
    openrouter_select: bool
    openrouter_months: int
    openrouter_temperature: float
    openrouter_max_tokens: Optional[int]
    openrouter_probe: bool
    judges_from_selection: bool
    openrouter_judge_months: Optional[int]
    openrouter_judge_max_tokens: Optional[int]
    topic_select: bool
    tui_wizard: bool
    prod_run: bool
    apply_stage_token_limits: bool
    skip_on_empty: bool
    quick_test: bool
    judges_test: bool
    resume: bool
    retry_failed: bool
    log_failed_judges: bool
    dry_run: bool
    postrate: bool
    postupload: bool
    postupload_bucket: Optional[str]
    postupload_prefix: str
    postupload_profile: Optional[str]
    postupload_region: Optional[str]
    postupload_include_artifacts: bool
    postupload_dry_run: bool
    estimate_time: bool


@dataclass
class RunSetup:
    """State assembled before scheduling/execution."""

    options: RunOptions
    settings: Settings
    main_cfg: cfg.MainConfig
    topics: List[cfg.Topic]
    debater_models: List[DebaterModelConfig]
    judge_models: List[JudgeModelConfig]
    topics_selected: List[cfg.Topic]
    run_tag: str
    debates_path: Path
    run_dir: Path
    viz_dir: Path
    plots_dir: Path
    ratings_path: Path
    snapshot_dir: Path
    cli_args_path: Path
    selection_snapshot_path: Path
    incremental_mode: bool
    append_slug: Optional[str]
    base_cli_args: Dict
    existing_records: List[DebateRecord]
    judge_output_max_tokens: Optional[int]
    rng: object


@dataclass
class RunPlan:
    """Concrete schedule inputs for execution."""

    topics_selected: List[cfg.Topic]
    pairs: List[Tuple[DebaterModelConfig, DebaterModelConfig]]
    debates_per_pair: int
    total_runs: int
    completed_counts: Dict[Tuple[str, str, str], int]
    tasks: List["DebateTask"] = field(default_factory=list)
    existing_completed: int = 0
    progress_path: Path | None = None
    schedule_preview: List[Dict] | None = None


@dataclass
class DebateTask:
    """A single debate instance (topic + ordered models + repetition index)."""

    topic: cfg.Topic
    pro_model: DebaterModelConfig
    con_model: DebaterModelConfig
    rep: int
    seed: int
    panel_configs: List[JudgeModelConfig] = field(default_factory=list)
    remaining_candidates: List[JudgeModelConfig] = field(default_factory=list)
    pair_key: str = ""
    task_id: str = ""


@dataclass
class JudgePanelPlan:
    """Planned judge panel for a debate, including alternates."""

    panel_configs: List[JudgeModelConfig]
    remaining_candidates: List[JudgeModelConfig]
    pair_key: str
