# DebateBench

Run debate-style LLM evaluations, collect judge scores, and compute Elo-style ratings with a reproducible CLI. Requires an OpenRouter API key and real model endpoints; there is no synthetic fallback path in the current CLI.

## Requirements
- Python 3.12
- Dependencies (installed via `pip install -e .`): Typer, Pydantic v2, pandas/seaborn/matplotlib.
- `.env` with `OPENROUTER_API_KEY` (required for real runs) and optional `OPENROUTER_SITE_URL` / `OPENROUTER_SITE_NAME` for referral headers.
- Optional AWS creds for `upload-results`.

## Install
```bash
pip install -e .
debatebench init   # writes configs/ and results/
```

## Quickstart
```bash
# edit configs/topics.json and configs/judges.yaml (or rely on interactive OpenRouter pickers)
debatebench run --sample-topics 3 --debates-per-pair 1 --run-tag demo
# artifacts land under results/: debates_demo.jsonl, viz_demo/, plots_demo/, ratings_demo.json
debatebench show-leaderboard --top 10
debatebench inspect-debate <debate_uuid>
```

## Command Map (full details in docs/cli-reference.md)
- `debatebench run` — orchestrate debates. Interactive topic/model/judge pickers are on by default; stage token limits come from `configs/config.yaml` (and can be overwritten per-run with `--apply-stage-token-limits --openrouter-max-tokens`). Judges can be balanced or random, and you can reuse debaters as judges with `--judges-from-selection` (active debaters are auto-excluded from the judge sample).
- `debatebench init` — create config templates and `results/`.
- `debatebench summarize` / `plot` — CSV summaries and PNG plots from a debates file.
- `debatebench rate` / `show-leaderboard` — recompute and view Elo.
- `debatebench inspect-debate` — print a single debate by ID (or latest).
- `debatebench upload-results` — push a file/dir to S3 with SSE-S3.
- All results utilities are also available as `debatebench results <command>`.

## Run Basics
- Seeded by default (`--seed 12345`) so side swaps, judge panels, and sampling are repeatable.
- Model discovery: OpenRouter catalog filtered to text-in/text-out from the last `--openrouter-months` (default 4). `--openrouter-probe` sanity-checks each model with a 1-token call and drops failures.
- Judge pool: either the selected debaters (`--judges-from-selection`) or a separate OpenRouter list. Balanced sampling (`--balanced-judges`, default) evens usage by topic/pair; random sampling is available.
- Stage token caps: defaults come from `configs/config.yaml` (parser treats nested-schema `max_tokens: null` as 5,000). `--apply-stage-token-limits` overwrites opening/rebuttal/closing to `--openrouter-max-tokens` for a run. If a round token limit ends up unset, the adapter falls back to model caps and then 1,024. Prompts still nudge ~700 tokens.
- Failure handling: empty turns trigger retries up to 5; `--skip-on-empty` bans a model for the remainder; `--retry-failed` retries failed debates once.
- Time/cost preview: `--dry-run` emits `results/run_<tag>/dryrun_schedule.json`, prints rough wall-clock and token-cost estimates (live OpenRouter pricing + optional activity snapshot), then exits. Real runs request per-call usage from OpenRouter and record observed USD cost on each turn/judge when returned.
- Incremental append: `--new-model <id> --run-tag <tag>` schedules only matchups involving the new model using the prior topics/pairs from `results/debates_<tag>.jsonl` and `results/run_<tag>/config_snapshot/*`.

## Outputs (results/)
- `debates_<tag>.jsonl` — one DebateRecord per line (transcript, judges, aggregate scores, timings, tokens).
- `viz_<tag>/` — CSVs from `summarize` (winner counts, topic win rates, per-dimension means, judge agreement, side winrates, timing/tokens, score gaps).
- `plots_<tag>/` — PNGs from `plot` matching the CSVs.
- `ratings_<tag>.json` — Elo ratings and per-dimension averages.
- `run_<tag>/config_snapshot/` — frozen `config/topics/models/judges` plus `cli_args*.json` and `effective_selection*.json`.
- `run_<tag>/dryrun_schedule.json` — full planned debates/judge panels for `--dry-run`.
- `run_<tag>/progress.json` — running totals and banned models; `failed_judges.jsonl` appears when `--log-failed-judges` is set.

## Where to go next
- CLI details: `docs/cli-reference.md`
- Config schema and prompts: `docs/config-guide.md`
- Troubleshooting: `docs/troubleshooting.md`
- Dashboard ingestion (Next.js): `docs/dashboard-ingestion.md`
