from __future__ import annotations

import random
from pathlib import Path

from debatebench import config as cfg
from debatebench.cli.run.planner import build_plan
from debatebench.cli.run.types import RunOptions, RunSetup
from debatebench.schema import DebaterModelConfig, JudgeModelConfig
from debatebench.settings import Settings


def _make_options():
    return RunOptions(
        config_path=Path("configs/config.yaml"),
        topics_path=Path("configs/topics.json"),
        models_path=Path("configs/models.yaml"),
        judges_path=Path("configs/judges.yaml"),
        debates_path_arg=Path("results/debates.jsonl"),
        run_tag="test",
        new_model_id="c",
        sample_topics=None,
        debates_per_pair=1,
        seed=12345,
        swap_sides=False,
        balanced_sides=False,
        side_policy=None,
        balanced_judges=True,
        judge_policy=None,
        openrouter_select=False,
        openrouter_months=1,
        openrouter_temperature=0.7,
        openrouter_max_tokens=None,
        openrouter_probe=False,
        judges_from_selection=True,
        openrouter_judge_months=None,
        openrouter_judge_max_tokens=None,
        topic_select=False,
        tui_wizard=False,
        ui=None,
        prod_run=False,
        apply_stage_token_limits=False,
        stage_max_tokens=None,
        skip_on_empty=False,
        quick_test=False,
        judges_test=False,
        resume=False,
        retry_failed=True,
        log_failed_judges=False,
        dry_run=False,
        postrate=False,
        postupload=False,
        postupload_bucket=None,
        postupload_prefix="",
        postupload_profile=None,
        postupload_region=None,
        postupload_include_artifacts=False,
        postupload_dry_run=False,
        estimate_time=False,
    )


def test_build_plan_incremental_filters_pairs(tmp_path):
    options = _make_options()
    main_cfg = cfg.default_main_config()
    main_cfg.num_judges = 2
    topics = [cfg.Topic(id="t1", motion="m1")]
    debaters = [
        DebaterModelConfig(id="a", provider="openrouter", model="a/model"),
        DebaterModelConfig(id="b", provider="openrouter", model="b/model"),
        DebaterModelConfig(id="c", provider="openrouter", model="c/model"),
    ]
    judges = [
        JudgeModelConfig(id="j1", provider="openrouter", model="j1/model"),
        JudgeModelConfig(id="j2", provider="openrouter", model="j2/model"),
    ]

    run_dir = tmp_path / "run_test"
    run_dir.mkdir()

    setup = RunSetup(
        options=options,
        settings=Settings(openrouter_api_key="key"),
        main_cfg=main_cfg,
        topics=topics,
        debater_models=debaters,
        judge_models=judges,
        topics_selected=topics,
        run_tag="test",
        debates_path=tmp_path / "debates_test.jsonl",
        run_dir=run_dir,
        viz_dir=tmp_path / "viz",
        plots_dir=tmp_path / "plots",
        ratings_path=tmp_path / "ratings.json",
        snapshot_dir=tmp_path / "snap",
        cli_args_path=tmp_path / "cli_args.json",
        selection_snapshot_path=tmp_path / "selection.json",
        incremental_mode=True,
        append_slug=None,
        base_cli_args={},
        existing_records=[],
        judge_output_max_tokens=None,
        rng=random.Random(123),
    )

    result = build_plan(setup, debates_per_pair=1)
    assert result.dry_run_only is False
    assert result.plan is not None
    pair_ids = {(t.pro_model.id, t.con_model.id) for t in result.plan.tasks}
    assert all("c" in pair for pair in pair_ids)
