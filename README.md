# DebateBench

CLI tool to run debate-style evaluations between LLM models, collect per-side judge scores, and maintain Elo-style ratings.

## Install

```bash
pip install -e .
```

Requires Python 3.9+.

Set credentials (for OpenAI provider):

```bash
echo 'OPENAI_API_KEY=sk-...' > .env
```

## CLI

- `debatebench init` — create `configs/` templates and `results/` directory.
- `debatebench run` — run debates for configured model pairs and topics, append to `results/debates.jsonl` (or `results/debates_<run_tag>.jsonl` when `--run-tag` is provided).
- `debatebench rate` — recompute Elo ratings from debate logs, write `results/ratings.json`.
- `debatebench show-leaderboard` — print sorted ratings with precomputed per-dimension averages.
- `debatebench inspect-debate <id>` — print a single debate transcript and judge outputs.
- `debatebench summarize` — write CSV summaries (winners, topic win rates, per-model dimension averages, judge agreement) to `results/viz/`.

## Quick visualization

- Notebook: `notebooks/viz.ipynb` plots the summary CSVs. Run after `debatebench summarize`.
- Script: `python scripts/plot_viz.py --viz-dir results/viz --out-dir results/plots` saves PNGs for winner distribution, topic win rates, per-model dimension averages, and judge agreement.

## Config files (in `configs/`)

- `config.yaml` — benchmark/rubric versions, **rounds (authoritative debate format; default is a minimal starter with two opening turns: Pro then Con, 4096 token limit)**, scoring dimensions (1–10 integers, per side), judge count (default 3), Elo settings (initial 400, K=32).
- `topics.json` — list of topics `{id, motion, category}`; empty by default.
- `models.yaml` — debater model entries `{id, provider, model, token_limit, endpoint, parameters}`; empty template.
- `judges.yaml` — judge model entries `{id, provider, model, endpoint, prompt_style, parameters}`; empty template.

Environment:
- `.env` (optional) — loaded automatically; set `OPENAI_API_KEY` (and optionally `HTTP_BEARER_TOKEN` for generic HTTP providers).

## Data files (in `results/`)

- `debates.jsonl` — one stored debate per line, including `benchmark_version`/`rubric_version`, full transcript with seed, raw judge outputs, and aggregated results. Each judge returns integer scores **per dimension per side (Pro and Con) plus a winner label**. A 3-judge panel is sampled from `judges.yaml`; winner is by majority vote (ties remain `tie`), per-dimension scores are averaged across judges per side.
- `ratings.json` — includes `benchmark_version`, `rubric_version`, Elo settings, and per-model entries: `rating`, `games_played`, and `dimension_avgs[dimension]` averaged over all debates the model participated in (using that model’s side-specific scores).

## Defaults and assumptions

- Minimal starter format: two opening turns (Pro then Con). **`rounds` is the source of truth—extend with rebuttals/closings as you evolve the format.**
- Scores are integers 1–10 per side per dimension.
- Panel of 3 judges sampled from the pool; majority vote for winner, mean scores per side.
- Elo start rating 400 (intentional placeholder; only differences matter), K-factor 32, chess-style expected score.
- Full prompts/responses and the random seed are logged per debate; model and judge calls are stubbed placeholders until real adapters are added.

## Next steps

1. Add real provider adapters for debaters and judges.
2. Populate `topics.json`, `models.yaml`, and `judges.yaml`.
3. Tune debate format, token limits, and Elo settings as desired.
