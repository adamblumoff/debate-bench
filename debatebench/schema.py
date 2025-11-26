"""
Typed data structures used across DebateBench.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RoundConfig(BaseModel):
    speaker: Literal["pro", "con"]
    stage: str
    token_limit: int = Field(default=4096, ge=1)
    language: str = "en"


class DimensionConfig(BaseModel):
    id: str
    name: Optional[str] = None


class ScoringConfig(BaseModel):
    dimensions: List[DimensionConfig]
    scale_min: int = 1
    scale_max: int = 10


class EloConfig(BaseModel):
    initial_rating: float = 400.0
    k_factor: float = 32.0


class MainConfig(BaseModel):
    benchmark_version: str = "v0"
    rubric_version: str = "v0"
    rounds: List[RoundConfig]
    scoring: ScoringConfig
    num_judges: int = 3
    elo: EloConfig = EloConfig()
    language: str = "en"


class Topic(BaseModel):
    id: str
    motion: str
    category: Optional[str] = None


class DebaterModelConfig(BaseModel):
    id: str
    provider: str
    model: str
    token_limit: Optional[int] = None
    endpoint: Optional[str] = None
    parameters: Dict[str, str] = Field(default_factory=dict)


class JudgeModelConfig(BaseModel):
    id: str
    provider: str
    model: str
    endpoint: Optional[str] = None
    prompt_style: Optional[str] = None
    token_limit: Optional[int] = None
    parameters: Dict[str, str] = Field(default_factory=dict)


class Turn(BaseModel):
    index: int
    speaker: Literal["pro", "con"]
    stage: str
    content: str
    created_at: datetime
    duration_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class Transcript(BaseModel):
    debate_id: str
    benchmark_version: str
    rubric_version: str
    topic: Topic
    pro_model_id: str
    con_model_id: str
    turns: List[Turn]
    seed: Optional[int] = None


class JudgeScores(BaseModel):
    scores: Dict[str, int]  # dimension id -> integer score


class JudgeResult(BaseModel):
    judge_id: str
    pro: JudgeScores
    con: JudgeScores
    winner: Literal["pro", "con", "tie"]
    raw_response: Optional[str] = None
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AggregatedResult(BaseModel):
    winner: Literal["pro", "con", "tie"]
    mean_pro: Dict[str, float]
    mean_con: Dict[str, float]


class DebateRecord(BaseModel):
    transcript: Transcript
    judges: List[JudgeResult]
    aggregate: AggregatedResult
    created_at: datetime


class RatingEntry(BaseModel):
    rating: float
    games_played: int
    dimension_avgs: Dict[str, float] = Field(default_factory=dict)


class RatingsFile(BaseModel):
    benchmark_version: str
    rubric_version: str
    elo: EloConfig
    models: Dict[str, RatingEntry]
