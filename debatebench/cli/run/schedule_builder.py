"""Schedule construction helpers for the `debatebench run` command."""
from __future__ import annotations

import random
from typing import Dict, Tuple

import typer

from ...schedule import derive_debate_seed, make_pair_key, select_judges
from .types import DebateTask


def build_schedule(
    *,
    setup,
    pairs,
    debates_per_pair: int,
    completed_counts: Dict[Tuple[str, str, str], int],
    judge_usage: Dict[str, int],
    include_completed: bool,
):
    opts = setup.options
    main_cfg = setup.main_cfg
    usage_counts = judge_usage.copy()
    topic_usage: dict[Tuple[str, str], int] = {}
    pair_usage: dict[Tuple[str, str], int] = {}
    preview: list[Dict] = []
    tasks = []
    for topic in setup.topics_selected:
        for (model_a, model_b) in pairs:
            already_done = completed_counts.get((topic.id, model_a.id, model_b.id), 0)
            for rep in range(debates_per_pair):
                if not include_completed and rep < already_done:
                    continue
                debate_seed = derive_debate_seed(setup.run_tag, topic.id, model_a.id, model_b.id, rep)
                debate_rng = random.Random(debate_seed)
                pro_model = model_a
                con_model = model_b
                if opts.side_policy == "random" and debate_rng.random() < 0.5:
                    pro_model, con_model = con_model, pro_model
                judge_source_pool = list(setup.judge_models)
                if opts.judges_from_selection:
                    judge_source_pool = [
                        j for j in setup.judge_models if j.id not in {pro_model.id, con_model.id}
                    ]
                pair_key = make_pair_key(pro_model.id, con_model.id)
                judges_chosen: list[str] = []
                panel_configs = []
                remaining_candidates = []
                if main_cfg.num_judges > 0:
                    if len(judge_source_pool) < main_cfg.num_judges:
                        if include_completed:
                            judges_chosen = ["<insufficient judges after exclusion>"]
                        else:
                            raise typer.BadParameter(
                                "Need at least "
                                f"{main_cfg.num_judges} judges after exclusions; found "
                                f"{len(judge_source_pool)}."
                            )
                    else:
                        panel_configs = select_judges(
                            judge_source_pool,
                            main_cfg.num_judges,
                            debate_seed,
                            usage_counts,
                                opts.judge_policy == "balanced",
                            topic_id=topic.id,
                            pair_key=pair_key,
                            topic_usage=topic_usage,
                            pair_usage=pair_usage,
                        )
                        judges_chosen = [j.id for j in panel_configs]
                        for j in panel_configs:
                            usage_counts[j.id] = usage_counts.get(j.id, 0) + 1
                            topic_usage[(j.id, topic.id)] = topic_usage.get((j.id, topic.id), 0) + 1
                            pair_usage[(j.id, pair_key)] = pair_usage.get((j.id, pair_key), 0) + 1
                        remaining_candidates = [
                            j for j in judge_source_pool if j.id not in {cfg.id for cfg in panel_configs}
                        ]
                preview.append(
                    {
                        "topic": topic.id,
                        "pro": pro_model.id,
                        "con": con_model.id,
                        "judges": judges_chosen,
                        "rep": rep,
                    }
                )
                task_id = f"{topic.id}|{pro_model.id}|{con_model.id}|{rep}"
                tasks.append(
                    DebateTask(
                        topic=topic,
                        pro_model=pro_model,
                        con_model=con_model,
                        rep=rep,
                        seed=debate_seed,
                        panel_configs=panel_configs,
                        remaining_candidates=remaining_candidates,
                        pair_key=pair_key,
                        task_id=task_id,
                    )
                )
    return preview, tasks


__all__ = ["build_schedule"]
