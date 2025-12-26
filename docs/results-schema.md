# Results Schema (Debate JSONL)

Each line in `debates_<tag>.jsonl` is a `DebateRecord`.

## DebateRecord (top-level)
- `transcript`: `Transcript` (topic, models, turns, versions)
- `judges`: list of `JudgeResult`
- `aggregate`: `AggregatedResult`
- `created_at`: ISO timestamp
- `judges_expected`, `judges_actual` (optional)
- `panel_complete`, `panel_latency_ms` (optional)
- `debate_seed` (optional)
- `elo` (optional config snapshot)

## Transcript
- `debate_id`
- `benchmark_version`, `rubric_version`
- `topic`: `{ id, motion, category? }`
- `pro_model_id`, `con_model_id`
- `turns`: list of `Turn`
- `seed` (optional)

## Turn
- `index`
- `speaker`: `pro` | `con`
- `stage`: string (`opening`, `rebuttal`, `closing`, etc.)
- `content`: response content (with `<END_OF_TURN>` stripped)
- `created_at`
- `duration_ms` (optional)
- `prompt_tokens`, `completion_tokens`, `total_tokens` (optional)
- `cost`, `currency` (optional)
- `cost_details`, `metadata` (optional)

## JudgeResult
- `judge_id`
- `pro`: `{ scores: { <dimension_id>: int } }`
- `con`: `{ scores: { <dimension_id>: int } }`
- `winner`: `pro` | `con` | `tie`
- `raw_response`: optional raw JSON/text (if logging is enabled)
- `latency_ms` (optional)
- `prompt_tokens`, `completion_tokens`, `total_tokens` (optional)
- `cost`, `currency` (optional)
- `cost_details`, `metadata` (optional)

## AggregatedResult
- `winner`: `pro` | `con` | `tie`
- `mean_pro`: mean per-dimension scores
- `mean_con`: mean per-dimension scores

## Notes
- Observed costs are used when available; otherwise cost fields may be absent.
- Category splits are only available if `topic.category` is set.
