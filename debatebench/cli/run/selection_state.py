"""Shared state container for selection flow helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict

from ... import config as cfg
from ...schema import DebateRecord, DebaterModelConfig, JudgeModelConfig


@dataclass
class SelectionState:
    main_cfg: cfg.MainConfig
    topics: List[cfg.Topic]
    debater_models: List[DebaterModelConfig]
    judge_models: List[JudgeModelConfig]
    topics_selected: List[cfg.Topic]
    debates_per_pair: Optional[int]
    base_cli_args: Dict
    existing_records: List[DebateRecord]
    judge_output_max_tokens: Optional[int]
    rng: object
