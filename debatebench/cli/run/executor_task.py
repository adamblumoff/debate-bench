"""Task helpers for the `debatebench run` executor."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ...debate import run_debate
from ...judge import run_judge_panel
from ...schema import DebateRecord


def run_debate_and_judge(
    *,
    setup,
    topic,
    pro_model,
    con_model,
    debate_seed: int,
    debater_adapters,
    judge_adapters,
    panel_configs,
    remaining_candidates,
    failed_judges_path,
    log,
    status_hook=None,
    progress_hook=None,
    judge_hook=None,
):
    main_cfg = setup.main_cfg
    pro_adapter = debater_adapters[pro_model.id]
    con_adapter = debater_adapters[con_model.id]

    transcript = run_debate(
        topic=topic,
        pro_adapter=pro_adapter,
        con_adapter=con_adapter,
        config=main_cfg,
        seed=setup.options.seed,
        log=log,
        progress_hook=progress_hook,
    )
    if status_hook:
        status_hook(phase="judging")

    panel_adapters = [judge_adapters[j.id] for j in panel_configs]
    remaining_adapters = [judge_adapters[j.id] for j in remaining_candidates]

    if log:
        log(f"  Judging with panel: {', '.join(j.id for j in panel_configs)}")

    usage_ordering = {cfg.id: 0 for cfg in panel_configs}
    usage_ordering.update({cfg.id: 1 for cfg in remaining_candidates})

    def sink_failed(payload):
        if not failed_judges_path:
            return
        failed_judges_path.parent.mkdir(parents=True, exist_ok=True)
        with failed_judges_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        **payload,
                        "debate_id": transcript.debate_id,
                        "topic": topic.id,
                        "pro": pro_model.id,
                        "con": con_model.id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )
            f.write("\n")

    judge_results, aggregate = run_judge_panel(
        candidate_adapters=panel_adapters + remaining_adapters,
        transcript=transcript,
        config=main_cfg,
        expected=main_cfg.num_judges,
        usage=usage_ordering,
        seed=debate_seed,
        log=log,
        failed_judges_sink=sink_failed if failed_judges_path else None,
        progress_hook=judge_hook,
    )

    panel_latency = sum(j.latency_ms for j in judge_results if j.latency_ms is not None)

    record = DebateRecord(
        transcript=transcript,
        judges=judge_results,
        aggregate=aggregate,
        created_at=datetime.now(timezone.utc),
        judges_expected=main_cfg.num_judges,
        judges_actual=len(judge_results),
        panel_complete=len(judge_results) == main_cfg.num_judges,
        panel_latency_ms=panel_latency,
        debate_seed=debate_seed,
        elo=main_cfg.elo,
    )
    return record, aggregate


__all__ = ["run_debate_and_judge"]
