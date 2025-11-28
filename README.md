# DebateBench

CLI tool for running debate-style evaluations between LLM models, collecting judge scores, and computing Elo-style ratings. Adapters for real models are supported (OpenAI and generic HTTP), but the defaults are **stubbed**; without configured endpoints you'll get synthetic debates and scores -- useful for flow testing, not benchmarking.

## Requirements
- Python 3.9+
- `.env` with `OPENROUTER_API_KEY` (required) and optional `OPENROUTER_SITE_URL` / `OPENROUTER_SITE_NAME` for referral headers.
- Plotting depends on pandas + seaborn + matplotlib (installed via project deps).

## Install
```bash
pip install -e .
```

## Quickstart
```bash
debatebench init                        # writes configs/ and results/
# edit configs/topics.json and configs/judges.yaml (debater models are picked interactively from OpenRouter)
debatebench run --sample-topics 3 --debates-per-pair 1 --run-tag demo
# run writes results/debates_demo.jsonl and auto-summarizes/plots to results/viz_demo and results/plots_demo
debatebench show-leaderboard --top 10
debatebench inspect-debate <debate_uuid>
```

## CLI Commands
- `debatebench init` -- generate default config templates and create `results/`.
- `debatebench run` -- execute debates for all model pairs/topics. Defaults: topic picker on, OpenRouter picker (text-in/text-out models from last 4 months), `high_tokens` stage limits (3200/2200/1400) with per-model token bumps, seed=12345. Judges can come from the debater pool (`--judges-from-selection`, default off) and, when enabled, the two active debaters are excluded from the judge sampler. Flags of note: `--dry-run` (plan only, shows cost using live OpenRouter pricing and writes `dryrun_schedule.json`), `--resume` (skip already-written debates), `--skip-on-empty`, `--run-tag`, `--sample-topics`, `--debates-per-pair`, `--balanced-sides/--no-balanced-sides`, `--swap-sides`, `--topic-select/--no-topic-select`, `--openrouter-months`, `--openrouter-max-tokens`, `--openrouter-judge-max-tokens`, `--no-openrouter-select`, `--no-judges-from-selection`, `--no-tui-wizard`. After a run, summaries/plots/ratings/leaderboard are generated automatically (disable with `--no-postrate`).
- `debatebench rate` -- recompute Elo ratings from a debates file.
- `debatebench show-leaderboard` -- print rankings (optionally `--top N`).
- `debatebench inspect-debate <uuid>` -- print one debate with judge outputs.
- `debatebench summarize` -- emit CSV summaries from a debates file.
- `debatebench plot` -- render PNGs from summary CSVs.

## Configuration Layout (`configs/`)
- `config.yaml` -- benchmark metadata, rounds (speaker/stage/token limit), scoring dimensions and scale, judge count, Elo settings. Judge prompt expects scores-only JSON; winner is derived by DebateBench.
- `topics.json` -- list of 25 topics `{id, motion, category}`; picked interactively by default before models.
- `models.yaml` -- debater model entries `{id, provider, model, endpoint, token_limit, parameters}`. Use `provider: openrouter`; the interactive picker builds these for you at run time if `--openrouter-select` is on (default).
- `judges.yaml` -- judge model entries (same shape) plus optional `prompt_style`; provider must be `openrouter`.
Note: Judge IDs must not overlap with debater IDs.

OpenRouter example (`models.yaml`):
```yaml
- id: gpt4o
  provider: openrouter
  model: openai/gpt-4o
  parameters:
    temperature: 0.7
```

## Outputs (`results/`)
- `debates_<tag>.jsonl` -- one `DebateRecord` per line (transcript, judges, aggregate scores, timings, token usage).
- `ratings_<tag>.json` -- Elo ratings and per-dimension averages.
- `viz_<tag>/` -- CSV summaries (winner counts, topic win rates, dimension averages, judge agreement, token usage, etc.).
- `plots_<tag>/` -- PNGs generated from the CSVs.
- `run_<tag>/config_snapshot/` -- copies of configs plus effective selection and CLI args.
- `run_<tag>/dryrun_schedule.json` -- dry-run schedule preview with per-debate judge panels.

## Current Status / Limitations
- OpenRouter-only adapters; ensure `OPENROUTER_API_KEY` is set.
- No automated tests yet; prefer `pytest` with seeded RNGs when adding coverage.
- Results files can grow quickly; avoid committing large `results/` artifacts or `.env`.
