# DebateBench

CLI tool for running debate-style evaluations between LLM models, collecting judge scores, and computing Elo-style ratings. Adapters for real models are supported (OpenAI and generic HTTP), but the defaults are **stubbed**; without configured endpoints you'll get synthetic debates and scores -- useful for flow testing, not benchmarking.

## Requirements
- Python 3.9+
- Optional: `.env` with `OPENAI_API_KEY` (for OpenAI provider) and/or `HTTP_BEARER_TOKEN` (for generic HTTP).
- Plotting depends on pandas + seaborn + matplotlib (installed via project deps).

## Install
```bash
pip install -e .
```

## Quickstart
```bash
debatebench init                        # writes configs/ and results/
# edit configs/topics.json, configs/models.yaml, configs/judges.yaml
debatebench run --sample-topics 3 --debates-per-pair 1 --run-tag demo
# run writes results/debates_demo.jsonl and auto-summarizes/plots to results/viz_demo and results/plots_demo
debatebench show-leaderboard --top 10
debatebench inspect-debate <debate_uuid>
```

## CLI Commands
- `debatebench init` -- generate default config templates and create `results/`.
- `debatebench run` -- execute debates for all model pairs and topics; accepts `--run-tag`, `--sample-topics`, `--debates-per-pair`, `--balanced-sides/--no-balanced-sides`, `--swap-sides`.
- `debatebench rate` -- recompute Elo ratings from a debates file.
- `debatebench show-leaderboard` -- print rankings (optionally `--top N`).
- `debatebench inspect-debate <uuid>` -- print one debate with judge outputs.
- `debatebench summarize` -- emit CSV summaries from a debates file.
- `debatebench plot` -- render PNGs from summary CSVs.

## Configuration Layout (`configs/`)
- `config.yaml` -- benchmark metadata, rounds (speaker/stage/token limit), scoring dimensions and scale, judge count, Elo settings.
- `topics.json` -- list of `{id, motion, category}`.
- `models.yaml` -- debater model entries `{id, provider, model, endpoint, token_limit, parameters}`.
- `judges.yaml` -- judge model entries (same shape) plus optional `prompt_style`.
Note: Judge IDs must not overlap with debater IDs.

## Outputs (`results/`)
- `debates_<tag>.jsonl` -- one `DebateRecord` per line (transcript, judges, aggregate scores, timings, token usage).
- `ratings.json` -- current Elo ratings and per-dimension averages.
- `viz_<tag>/` -- CSV summaries (winner counts, topic win rates, dimension averages, judge agreement, token usage, etc.).
- `plots_<tag>/` -- PNGs generated from the CSVs.

## Current Status / Limitations
- Default adapters return stub text and synthetic scores; configure real endpoints for meaningful results.
- No automated tests yet; prefer `pytest` with seeded RNGs when adding coverage.
- Results files can grow quickly; avoid committing large `results/` artifacts or `.env`.
