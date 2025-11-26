# DebateBench

CLI tool to run debate-style evaluations between LLM models, collect judge scores, and maintain Elo-style ratings.

## Install

```bash
pip install -e .
```

Requires Python 3.9+.

## CLI

- `debatebench init` — create `configs/` templates and `results/` directory.
- `debatebench run` — run debates for configured model pairs and topics, append to `results/debates.jsonl`.
- `debatebench rate` — recompute Elo ratings from debate logs, write `results/ratings.json`.
- `debatebench show-leaderboard` — print sorted ratings with per-dimension averages.
- `debatebench inspect-debate <id>` — print a single debate transcript and judge outputs.

## Config files (in `configs/`)

- `config.yaml` — benchmark/rubric versions, rounds (default: two opening turns, Pro then Con, 4096 token limit), scoring dimensions (1–10 integers), judge count (3), Elo settings (initial 400, K=32).
- `topics.json` — list of topics `{id, motion, category}`; empty by default.
- `models.yaml` — debater model entries `{id, provider, model, token_limit, endpoint, parameters}`; empty template.
- `judges.yaml` — judge model entries `{id, provider, model, endpoint, prompt_style, parameters}`; empty template.

## Data files (in `results/`)

- `debates.jsonl` — one stored debate per line: transcript, judge panel outputs, aggregated winner and mean scores.
- `ratings.json` — ratings per model with games played and per-dimension averages (precomputed).

## Defaults and assumptions

- One debate format: two turns (Pro opening, Con opening) per debate; adjust `rounds` in `config.yaml` as needed.
- Scores are integers 1–10.
- Elo start rating 400, K-factor 32, chess-style expected score.
- Full prompts/responses logged; model and judge calls are stubbed placeholders until real adapters are added.

## Next steps

1. Add real provider adapters for debaters and judges.
2. Populate `topics.json`, `models.yaml`, and `judges.yaml`.
3. Tune debate format, token limits, and Elo settings as desired.
