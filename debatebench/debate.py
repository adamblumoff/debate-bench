"""
Debate orchestration.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional
import time

from .models import DebaterAdapter
from .schema import MainConfig, Topic, Transcript, Turn


def _build_prompt(topic: Topic, stage: str, speaker: str, turns: List[Turn]) -> str:
    history = "\n".join(f"{t.speaker.upper()}: {t.content}" for t in turns)
    prompt_parts = [
        f"Motion: {topic.motion}",
        f"Role: {speaker}",
        f"Stage: {stage}",
    ]
    if history:
        prompt_parts.append("History:\n" + history)
    return "\n".join(prompt_parts)


def run_debate(
    topic: Topic,
    pro_adapter: DebaterAdapter,
    con_adapter: DebaterAdapter,
    config: MainConfig,
    seed: Optional[int] = None,
    log=None,
) -> Transcript:
    """
    Orchestrate a debate transcript according to the configured rounds.
    """
    turns: List[Turn] = []
    debate_id = str(uuid.uuid4())

    adapter_map = {"pro": pro_adapter, "con": con_adapter}

    for idx, round_cfg in enumerate(config.rounds):
        speaker = round_cfg.speaker
        adapter = adapter_map[speaker]
        if log:
            log(f"  Turn {idx+1}: {speaker.upper()} ({round_cfg.stage})")
        prompt = _build_prompt(topic, round_cfg.stage, speaker, turns)

        # Retry a couple times if the model returns empty content.
        content = ""
        usage = {}
        attempts = 0
        while attempts < 2:
            attempts += 1
            t0 = time.perf_counter()
            content, usage = adapter.generate(prompt, turns, max_tokens=round_cfg.token_limit)
            duration_ms = (time.perf_counter() - t0) * 1000
            if content and content.strip():
                break
            if log:
                log(f"    Empty response from {speaker}; retrying ({attempts}/2)...")
            time.sleep(0.1)
        if not content or not content.strip():
            raise RuntimeError(f"{speaker} returned empty content after retries.")

        turn = Turn(
            index=idx,
            speaker=speaker,
            stage=round_cfg.stage,
            content=content,
            created_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            prompt_tokens=usage.get("prompt_tokens") if usage else None,
            completion_tokens=usage.get("completion_tokens") if usage else None,
            total_tokens=usage.get("total_tokens") if usage else None,
        )
        turns.append(turn)

    return Transcript(
        debate_id=debate_id,
        benchmark_version=config.benchmark_version,
        rubric_version=config.rubric_version,
        topic=topic,
        pro_model_id=pro_adapter.config.id,
        con_model_id=con_adapter.config.id,
        turns=turns,
        seed=seed,
    )
