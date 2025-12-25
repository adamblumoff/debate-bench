# DebateBench CLI Reference

Authoritative reference for every `debatebench` command and option. Defaults reflect the current code (Python 3.9+, Typer).

## Conventions
- Defaults shown in parentheses.
- Paths are workspace-relative unless noted.
- Seeded randomness: runs are repeatable by default (`--seed 12345`). Use a different integer seed to vary sampling/swaps.
- Tags: if you omit `--run-tag`, a UTC timestamp `run-YYYYMMDD-HHMMSS` is used to suffix outputs.

---

## `debatebench run`
Run debates for selected topics and model pairs, then (by default) summarize, plot, and rate. When an OpenRouter API key is present we request per-call usage (`usage.include=true`), record observed USD cost on each turn/judge, and reuse it in summaries/dashboard; if OpenRouter omits it we fall back silently to token counts.

**Core options**
- `--run-tag TEXT` — run tag for outputs. If omitted, a UTC timestamp `run-YYYYMMDD-HHMMSS` is generated.
- Outputs always use the resolved tag: `results/debates_<tag>.jsonl`, `results/viz_<tag>/`, `results/plots_<tag>/`, `results/ratings_<tag>.json`, `results/run_<tag>/...`.
- `--debates-per-pair INT` — debates per ordered model pair per topic. Default 1 (or inferred when `--new-model`).
- `--sample-topics INT` — randomly sample this many topics (after interactive selection).
- `--seed INT` — RNG seed (12345).
- `--balanced-sides / --no-balanced-sides` — permutations (A vs B and B vs A) vs combinations (A vs B only). Default balanced.
- `--swap-sides` — when not balanced, randomly swap pro/con per debate.

**Selection**
- `--openrouter-select / --no-openrouter-select` — interactive debater picker from OpenRouter (default on). If off, uses `configs/models.yaml`.
- `--openrouter-months INT` — catalog lookback in months (4).
- `--openrouter-probe / --no-openrouter-probe` — 1-token probe per selected model; failures are dropped (default on).
- `--topic-select / --no-topic-select` — interactive topic picker (default on).
- `--tui-wizard / --no-tui-wizard` — curses wizard that combines topic/model/judge selection (default on; falls back to prompts if curses unavailable).
- `--prod-run / --no-prod-run` — config-only mode: disables interactive selection and forces balanced judges + judges-from-selection.
- `--judges-from-selection` — reuse selected debaters as judge pool; active debaters in a debate are excluded from sampling.
- `--openrouter-judge-months INT` — judge catalog lookback (defaults to `--openrouter-months`).

**Token/temperature**
- `--openrouter-temperature FLOAT` — temperature for OpenRouter-selected debaters (0.7). Judges are forced to temperature 0.0 in the adapter.
- `--openrouter-max-tokens INT` — token limit assigned to OpenRouter-selected debater configs. To actually cap debate turns, also pass `--apply-stage-token-limits` (otherwise per-round caps come from `configs/config.yaml`).
- `--openrouter-judge-max-tokens INT` — max tokens assigned to OpenRouter-selected judges (and quick-test judges). If you run with `--no-openrouter-select`, set judge caps in `configs/judges.yaml` (`token_limit` / `parameters.max_tokens`).
- `--apply-stage-token-limits` — overwrite per-round token limits for opening/rebuttal/closing to `--openrouter-max-tokens` for this run.

**Judging**
- `--balanced-judges / --random-judges` — balanced uses least-used-first, further balancing by topic and pair; random is uniform. Default balanced.
- `--log-failed-judges` — append raw judge failures to `results/run_<tag>/failed_judges.jsonl`.
- `--skip-on-empty` — if a debater returns empty content after retries, ban that model for the rest of the run instead of aborting.
- `--retry-failed / --no-retry-failed` — retry failed debates once after the main loop. Default retry.

**Execution control**
- `--resume` — skip debates already present in the debates file (useful after interruption).
- `--dry-run` — plan only: prints cost/time estimates, writes `results/run_<tag>/dryrun_schedule.json`, and exits before any debates.
- `--estimate-time / --no-estimate-time` — show wall-clock estimate from timing snapshots (p50/p75/p90) when available; falls back to recent medians (default on). Estimates are rough and may be inaccurate.
- `--postrate / --no-postrate` — after finishing debates, recompute ratings and show top 10. Default on.
- `--postupload / --no-postupload` — after postrun, upload results to S3 (default on).
- `--postupload-bucket TEXT` — S3 bucket for `--postupload` (optional; defaults from env or `debatebench-results`).
- `--postupload-prefix TEXT` — key prefix inside the bucket (optional; defaults from env or `runs/<run_tag>`).
- `--postupload-profile TEXT` — AWS profile to use (optional; defaults from env; leave unset for Railway buckets).
- `--postupload-region TEXT` — AWS region override (optional; defaults from env).
- `--postupload-include-artifacts` — also upload `run_<tag>/`, `viz_<tag>/`, `plots_<tag>/`, and `ratings_<tag>.json` if present (default off).
- `--postupload-dry-run` — list postupload keys without sending.
- `--quick-test` — quick smoke test: random topic(s) and predefined debaters/judges from `configs/quick-test-models.yaml`; disables postupload and skips summaries/plots. Timing snapshots and ratings can still run.
- `--judges-test` — judge-focused smoke: 1 topic, fixed debaters (Haiku vs Gemini 2.5 Flash Lite), judges (Gemini 3 Pro, GPT-5.1); balanced sides off.

**Incremental append**
- `--new-model TEXT` — append only matchups involving this debater to an existing run.
- Requires: `--run-tag <tag>`, existing `results/debates_<tag>.jsonl`, and `results/run_<tag>/config_snapshot/{cli_args.json,effective_selection.json}`.
- Inferred: topics, debates-per-pair, sides orientation, judge settings from the snapshot/log.

**Paths**
- `--config-path PATH` (`configs/config.yaml`)
- `--topics-path PATH` (`configs/topics.json`)
- `--models-path PATH` (`configs/models.yaml`)
- `--judges-path PATH` (`configs/judges.yaml`)
- `--debates-path PATH` (`results/debates.jsonl`; only the directory is used — the output file is always named `debates_<run_tag>.jsonl`)

---

## `debatebench init`
Create default `configs/` templates and `results/`.
- `--force / -f` — overwrite existing templates.

---

## `debatebench summarize`
Emit CSV summaries from a debates file to `results/viz` by default.
- `--debates-path PATH` — debates file (default `results/debates.jsonl`).
- `--out-dir PATH` — output directory (default `results/viz`).
- Outputs: `winner_counts.csv`, `topic_winrate.csv`, `model_dimension_avg.csv`, `judge_agreement.csv`, `judge_side_preference.csv`, `judge_majority_alignment.csv`, `model_winrate_by_side.csv`, `dimension_score_gaps.csv`, `turn_timings.csv`, `token_usage.csv`, `cost_usage.csv` (observed mean USD per side when available).

---

## `debatebench plot`
Render PNG plots from the CSVs produced by `summarize`.
- `--viz-dir PATH` — input CSV dir (default `results/viz`).
- `--out-dir PATH` — output PNG dir (default `results/plots`).
- Plots: winner_counts.png, topic_winrate.png, model_dimension_heatmap.png, judge_agreement.png, judge_majority_alignment.png, judge_side_preference.png, model_winrate_by_side.png, dimension_score_gaps.png, turn_timings.png, token_usage.png, cost_usage.png (if cost CSV exists).

---

## `debatebench rate`
Recompute Elo ratings from debates.
- `--debates-path PATH` (`results/debates.jsonl`)
- `--config-path PATH` (`configs/config.yaml`)
- `--ratings-path PATH` (`results/ratings.json`)
- Output: ratings JSON with per-model games played and per-dimension averages.

---

## `debatebench show-leaderboard`
Print ratings table (Rich).
- `--ratings-path PATH` (`results/ratings.json`)
- `--top INT` — show only top N.

---

## `debatebench inspect-debate`
Print a single debate and judge decisions.
- Argument: `debate_id` (optional).
- `--debates-path PATH` — debates file (default `results/debates.jsonl`).
- `--latest` — auto-pick newest `debates_*.jsonl` and newest debate ID.
- Output: motion, pro/con IDs, transcript, judges, aggregate winner.

---

## `debatebench upload-results`
Upload a file or directory tree to S3 with SSE-S3.
- `--source PATH` — file or directory (default `results`).
- `--bucket TEXT` — target bucket (optional; defaults from env or `debatebench-results`).
- `--prefix TEXT` — key prefix (optional).
- `--profile TEXT` — AWS profile (optional).
- `--region TEXT` — AWS region override (optional).
- `--endpoint-url TEXT` — custom S3-compatible endpoint (optional; used for Railway buckets, MinIO, etc.).
- `--force-path-style / --no-force-path-style` — force path-style addressing for S3-compatible endpoints (optional; inferred for Railway).
- `--dry-run` — list uploads without sending.

---

## Results sub-app alias
All results utilities are also available under `debatebench results <command>`:
- `rate`, `show-leaderboard`, `inspect-debate`, `summarize`, `plot`, `upload-results`.

---

## Behavior notes (helpful defaults)
- Debater turns: per-round token caps come from `configs/config.yaml`. In the nested schema, `debate.rounds[].max_tokens: null` is treated as 5,000 by the parser. The debater adapter fallback to 1,024 only matters if a round token limit ends up unset (e.g., by applying stage limits without setting `--openrouter-max-tokens`).
- Judge temperature is forced to 0.0; judge responses are validated against a strict JSON schema. Non-JSON fallbacks are parsed best-effort; all-minimum-score replies are rejected.
- Balanced judge sampling prioritizes least-used overall, then least-used for the topic and pair; random is uniform.
- Progress and failures: live view shows active debates, per-debate rounds, judging progress, retries, and rate-limit/backoff status. `results/run_<tag>/progress.json` tracks counts and banned models; `results/run_<tag>/failed_judges.jsonl` appears when `--log-failed-judges` is set.
- Timing snapshots: `results/run_<tag>/timing_snapshot.json` is written after each run and feeds `--estimate-time`.
- Resume: `--resume` and incremental append both rely on the debates file; planning skips already-completed topic/pair/rep combos.
