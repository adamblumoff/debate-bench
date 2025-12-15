# Artifacts and File Map

Where DebateBench writes outputs and what each file contains.

## Top-level
- `results/` — all run outputs live here.
- `configs/` — inputs and snapshots (copied into each `results/run_<tag>/config_snapshot/`).

## Per-run outputs (tag = run name or timestamp)
- `results/debates_<tag>.jsonl` — append-only debate records (one JSON per line).
- `results/viz_<tag>/` — CSV summaries produced by `summarize`.
- `results/plots_<tag>/` — PNG plots produced by `plot`.
- `results/ratings_<tag>.json` — Elo ratings from `rate`.
- `results/run_<tag>/` — run-scoped metadata:
  - `config_snapshot/` — frozen copies of `config.yaml`, `topics.json`, `models.yaml`, `judges.yaml`, plus `cli_args*.json` and `effective_selection*.json` (append mode writes `*_append_<model>.json`).
  - `dryrun_schedule.json` — full planned debates and judge panels (only when `--dry-run`).
  - `progress.json` — rolling counters (completed prior/new, total planned, banned models, timestamp).
  - `failed_judges.jsonl` — judge failures when `--log-failed-judges` is enabled.

## Debate record (JSONL)
Each line is a `DebateRecord`:
- `transcript`: debate_id, topic {id,motion,category}, pro_model_id, con_model_id, turns[] (speaker, stage, content, timestamps, token usage, raw_response/reasoning in metadata).
- `judges`: list of judge results with per-dimension integer scores, winner, latency, token usage, raw_response.
- `aggregate`: panel winner (majority vote) and per-dimension mean scores for pro/con.
- `created_at`, `judges_expected/actual`, `panel_complete`, `panel_latency_ms`, `debate_seed`, `elo` config snapshot.

## CSV schemas (viz_<tag>/)
- `winner_counts.csv`: winner,count
- `topic_winrate.csv`: topic_id,pro_wins,con_wins,ties,total
- `model_dimension_avg.csv`: model_id,dimension,mean_score,samples
- `judge_agreement.csv`: judge_a,judge_b,agree,total,agreement_rate
- `judge_side_preference.csv`: judge_id,pro,con,tie,total,pro_rate,con_rate,tie_rate
- `judge_majority_alignment.csv`: judge_id,matches_majority,total,alignment_rate
- `model_winrate_by_side.csv`: model_id,pro_w,pro_l,pro_t,con_w,con_l,con_t
- `dimension_score_gaps.csv`: debate_id,dimension,gap (mean_pro - mean_con)
- `turn_timings.csv`: model_id,side,mean_ms,samples
- `token_usage.csv`: model_id,side,mean_prompt_tokens,mean_completion_tokens,samples
- `cost_usage.csv`: model_id,side,mean_cost_usd,samples (only includes observed costs when present in the JSONL)

## PNG plots (plots_<tag>/)
- winner_counts.png
- topic_winrate.png
- model_dimension_heatmap.png
- judge_agreement.png
- judge_majority_alignment.png
- judge_side_preference.png (if CSV exists)
- model_winrate_by_side.png
- dimension_score_gaps.png
- turn_timings.png
- token_usage.png
- cost_usage.png (if CSV exists)

## Progress and diagnostics
- `progress.json` example:
```json
{
  "run_tag": "demo",
  "debates_file": "results/debates_demo.jsonl",
  "total_planned_remaining": 60,
  "completed_new": 12,
  "completed_prior": 0,
  "completed_total": 12,
  "timestamp": "2025-12-10T02:30:00Z",
  "banned_models": ["deepseek-deepseek-v3.2"]
}
```
- `failed_judges.jsonl` rows include judge_id, error, debate_id, topic, pro, con, created_at.

## S3 uploads
`debatebench upload-results` preserves directory structure; keys are `prefix/relative/path`. It targets any S3-compatible bucket (AWS, Railway, MinIO); SSE-S3 is attempted when supported.
