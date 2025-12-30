"""Round-order helpers for DebateBench runs."""
from __future__ import annotations

from typing import Iterable

from ...schema import RoundConfig, Transcript


def infer_round_order_from_rounds(rounds: Iterable[RoundConfig]) -> str:
    rounds_list = list(rounds)
    if not rounds_list:
        return "unknown"
    return "con-first" if rounds_list[0].speaker == "con" else "pro-first"


def infer_round_order_from_transcript(transcript: Transcript) -> str:
    if getattr(transcript, "round_order", None):
        return transcript.round_order  # type: ignore[return-value]
    if transcript.turns:
        return "con-first" if transcript.turns[0].speaker == "con" else "pro-first"
    return "unknown"


def flip_round_speakers(rounds: Iterable[RoundConfig]) -> list[RoundConfig]:
    flipped = []
    for r in rounds:
        speaker = "con" if r.speaker == "pro" else "pro"
        flipped.append(r.model_copy(update={"speaker": speaker}))
    return flipped


__all__ = [
    "infer_round_order_from_rounds",
    "infer_round_order_from_transcript",
    "flip_round_speakers",
]
