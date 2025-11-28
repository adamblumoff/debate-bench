"""
Debate orchestration.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional
import time

import re

from .models import DebaterAdapter
from .schema import MainConfig, Topic, Transcript, Turn


class EmptyResponseError(RuntimeError):
    def __init__(self, model_id: str, stage: str, speaker: str):
        super().__init__(f"{model_id} returned empty content after retries.")
        self.model_id = model_id
        self.stage = stage
        self.speaker = speaker


def _build_prompt(topic: Topic, stage: str, speaker: str, turns: List[Turn], config: MainConfig) -> str:
    """
    Construct a single-turn prompt that includes the authored system prompt,
    stage framing, prior turns, and explicit turn-ending marker to discourage meta-planning.
    """
    role_prompt = config.system_prompt_pro if speaker == "pro" else config.system_prompt_con
    history = "\n".join(f"{t.speaker.upper()} ({t.stage}): {t.content}" for t in turns)
    stage_guidance = {
        "opening": "Opening: lay out your main case and thesis clearly.",
        "rebuttal": "Rebuttal: directly refute the opponent's key points while reinforcing your own.",
        "closing": "Closing: summarize the debate, compare both sides, and explain why your side should win.",
    }.get(stage, f"{stage.title()}: provide your argument for this stage.")
    instructions = (
        "You are speaking now. Deliver the speech for this stage only. "
        "Do not include planning notes or statements like 'I'm going to'. "
        "Write 2-4 concise paragraphs. End your reply with <END_OF_TURN>."
    )
    parts = []
    if role_prompt:
        parts.append(role_prompt.strip())
    parts.append(f"Motion: {topic.motion}")
    parts.append(f"Role: {speaker.upper()}")
    parts.append(f"Stage: {stage}")
    parts.append(stage_guidance)
    parts.append(instructions)
    if history:
        parts.append("History:\n" + history)
    return "\n\n".join(parts)


def _strip_end_marker(text: str) -> str:
    return text.replace("<END_OF_TURN>", "").strip()


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

    max_attempts = 5

    for idx, round_cfg in enumerate(config.rounds):
        speaker = round_cfg.speaker
        adapter = adapter_map[speaker]
        if log:
            log(f"  Turn {idx+1}: {speaker.upper()} ({round_cfg.stage})")
        prompt = _build_prompt(topic, round_cfg.stage, speaker, turns, config)

        # Retry if the model returns empty content or meta/planning instead of a speech.
        content = ""
        usage = {}
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            t0 = time.perf_counter()
            content, usage = adapter.generate(prompt, turns, max_tokens=round_cfg.token_limit)
            duration_ms = (time.perf_counter() - t0) * 1000

            # If content is empty but reasoning was returned (thinking routes), synthesize from reasoning.
            content_from_reasoning = False
            if (not content or not content.strip()) and usage and usage.get("reasoning"):
                content = usage.get("reasoning") or ""
                if content:
                    content = content + "\n<END_OF_TURN>"
                    content_from_reasoning = True

            if content and content.strip():
                # If model omitted the marker, append it for convenience.
                if "<END_OF_TURN>" not in content:
                    content = content.rstrip() + "\n<END_OF_TURN>"
                content_clean = _strip_end_marker(content)
                content = content_clean
                break
            if log:
                log(f"    Empty response from {speaker}; retrying ({attempts}/{max_attempts})...")
            time.sleep(0.1)
        if not content or not content.strip():
            raise EmptyResponseError(adapter.config.id, round_cfg.stage, speaker)

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
            # stash raw model response and reasoning when available
            metadata={
                "raw_response": usage.get("raw_response"),
                "reasoning": usage.get("reasoning"),
            }
            if usage
            else None,
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
