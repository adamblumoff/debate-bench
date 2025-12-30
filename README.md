# DebateBench

DebateBench is a debate-tournament evaluation harness for LLMs. It uses LLM judges and subjective scoring dimensions to measure debate performance and surface behavioral trade-offs. It is judge-driven and preference-based. Not an accuracy benchmark. Not affiliated with the academic dataset also called DebateBench.

## What It Measures (and What It Does Not)
**Measures**
- Persuasive effectiveness in adversarial debate.
- Reasoning quality as perceived by judges in the debate setting.
- Groundedness-perception (perceived factuality/groundedness, not “truth”).
- Clarity and organization of arguments.
- Safety posture under the protocol (avoidance of unsafe or rule-violating content).

**Does NOT measure**
- Factual correctness in a ground-truth sense.
- Real-world competence or task performance outside debate.
- Safety compliance guarantees or policy adherence in deployment.
- Agentic tool behavior or tool use reliability.
- Production readiness, latency SLAs, or cost efficiency guarantees.

## Core Concepts
**Debate protocol**
- Opening → rebuttal → closing, with explicit PRO/CON roles.
- Rounds, temperature, and token budgets come from `configs/config.yaml` (`debate.rounds`, `debate.temperature`).

**Judges**
- N judges per debate (`scoring.judges_per_debate` or `num_judges`).
- Each judge returns structured JSON scores; the judge prompt is part of the benchmark (`scoring.judge_system_prompt`).
- Judge temperature is forced to 0.0 for deterministic scoring.

**Dimensions**
- Default dimensions in `configs/config.yaml`: persuasiveness, reasoning, factuality, clarity, safety.
- “Factuality” should be interpreted as perceived factuality/groundedness. You can rename the dimension id in config if you prefer `groundedness` as the label.

**Winner derivation (exact rule)**
Per-judge winner from dimension means (see `debatebench/judge.py`):
```text
pro_avg = mean(scores.pro[dim] for dim in dimensions)
con_avg = mean(scores.con[dim] for dim in dimensions)
judge_winner = "pro" if pro_avg > con_avg else "con" if con_avg > pro_avg else "tie"
```
Panel winner is a majority vote over judge_winner labels:
```text
panel_winner = "pro" if pro_votes > con_votes
             = "con" if con_votes > pro_votes
             = "tie" otherwise
```
Aggregate mean scores per dimension are the simple average of judge scores for each side.

**Ratings (Elo)**
Elo and win rates are secondary relationships (aggregates) derived from judge outcomes. Elo is computed from panel winners (see `debatebench/rating.py`):
```text
expected = 1 / (1 + 10^((r_con - r_pro) / 400))
score_pro = 1 if winner == "pro" else 0 if winner == "con" else 0.5
r_pro' = r_pro + K * (score_pro - expected)
r_con' = r_con - K * (score_pro - expected)
```
Defaults come from `configs/config.yaml`: `initial_rating` (400), `k_factor` (32), `min_games_for_display` (5). The leaderboard hides models with fewer than `min_games_for_display` games.

**Derived metrics (summaries)**
From `debatebench summarize` (see `debatebench/cli/summarize.py`):
- Judge agreement: for each judge pair, `agreement_rate = agree / total`, where `agree` is the number of panels where both judges chose the same winner label.
- Judge side preference: per judge, counts of pro/con/tie winners and rates `pro_rate = pro / total`, `con_rate = con / total`, `tie_rate = tie / total`.
- Side bias by model: `model_winrate_by_side.csv` records counts of wins/losses/ties separately when a model is PRO vs CON, based on the panel winner.

## How to Interpret Results
- Elo is a compact summary of win/loss outcomes, not a ground-truth skill measure.
- Win rate and Elo can disagree because of strength of schedule and non-transitive matchups.
- Side bias matters: compare PRO vs CON win rates (`model_winrate_by_side.csv`) to interpret stance robustness.
- Judge agreement reflects how often judges pick the same winner (`judge_agreement.csv`). Low agreement means the panel finds the debate ambiguous or the rubric is underspecified; disagreement is expected.
- Cost and tokens are workload signals. Later rounds can cost more (longer transcripts, more context). Verbosity can influence perceived scores and costs even if content quality does not improve.

**Example secondary insights**
- Stance robustness: does a model win similarly as PRO and CON?
- Judge sensitivity: which judges systematically diverge from the panel majority?
- Domain persuasion differences: topic-level win rates by category.
- Verbosity dependence: do scores correlate with higher token usage?
- Cost–performance trade-off: Elo or win rate per observed USD.

## Reproducibility and Provenance
**What to version or store per run**
- Model IDs and versions (debaters and judges).
- Debate prompts (system prompts + judge prompt).
- Topic set and sampling seed.
- Judge models and panel size (`num_judges`).
- Temperature and token budgets.
- Harness version/commit (code used to run the benchmark).

**Artifacts and where they live**
- `results/debates_<tag>.jsonl` — transcripts, judges, aggregate scores, usage/costs, metadata.
- `results/viz_<tag>/` — CSV summaries (win counts, win rates, dimension means, judge agreement, side win rates, timing/tokens, score gaps).
- `results/plots_<tag>/` — PNG plots from the CSVs.
- `results/ratings_<tag>.json` — Elo ratings and per-dimension averages.
- `results/run_<tag>/config_snapshot/` — frozen `config.yaml`, `topics.json`, `models.yaml`, `judges.yaml`, plus `cli_args*.json` and `effective_selection*.json`.
- `results/run_<tag>/dryrun_schedule.json` — full planned schedule when using `--dry-run`.
- `results/run_<tag>/progress.json` and optional `failed_judges.jsonl` when logging failures.

**How to compare runs responsibly**
- Keep judge models and judge prompt constant.
- Keep topics and sampling seed constant.
- Match debate protocol (rounds, temperature, token caps).
- Note model/version drift and OpenRouter pricing or policy changes.

## Best Practices / Limitations / Failure Modes
- Prompt sensitivity: small prompt tweaks can change outcomes.
- Judge bias: judges may favor certain styles or stances.
- Verbosity bias: longer answers can appear stronger (and cost more).
- Side order effects: opening order and side assignment matter.

**Optional robustness checks**
- Role swapping: run both PRO and CON assignments.
- Judge blinding: diversify judge models and avoid overlap with debaters.

**Do not use for**
- Hiring or performance evaluations of people.
- Safety certification or compliance claims.
- Claims of factual truthfulness or real-world competence.

## Quickstart
```bash
pip install -e .
debatebench init

# Run a small demo (interactive model/topic/judge selection is on by default)
debatebench run --sample-topics 3 --debates-per-pair 1 --run-tag demo

debatebench show-leaderboard --top 10
```
Outputs land under `results/`: `debates_demo.jsonl`, `viz_demo/`, `plots_demo/`, `ratings_demo.json`, `run_demo/`.

**Minimal config snippet** (`configs/config.yaml`)
```yaml
benchmark:
  name: "DebateBench"
  version: "v0.1"

debate:
  temperature: 0.7
  rounds:
    - role: pro
      stage: opening
      max_tokens: 4096
    - role: con
      stage: opening
      max_tokens: 4096
    - role: pro
      stage: rebuttal
      max_tokens: 4096
    - role: con
      stage: rebuttal
      max_tokens: 4096
    - role: pro
      stage: closing
      max_tokens: 4096
    - role: con
      stage: closing
      max_tokens: 4096

scoring:
  dimensions:
    persuasiveness: {min: 1, max: 10, description: "..."}
    reasoning: {min: 1, max: 10, description: "..."}
    factuality: {min: 1, max: 10, description: "..."}
    clarity: {min: 1, max: 10, description: "..."}
    safety: {min: 1, max: 10, description: "..."}
  judges_per_debate: 3
  judge_system_prompt: |
    You are an expert debate adjudicator. ...

elo:
  initial_rating: 400
  k_factor: 32
  min_games_for_display: 5
```

**Select models, judges, and topics**
```yaml
# configs/models.yaml
models:
  - id: openai-gpt-5.1
    provider: openrouter
    model: openai/gpt-5.1
    parameters: {temperature: 0.7}

# configs/judges.yaml
judges:
  - id: anthropic-claude-sonnet-4.5
    provider: openrouter
    model: anthropic/claude-sonnet-4.5
    parameters: {temperature: 0.0}
```

```json
// configs/topics.json
[
  {"id": "t001", "motion": "Governments should ...", "category": "policy"}
]
```

**Launch the dashboard** (optional)
```bash
cd dashboard
cp .env.example .env
pnpm install
pnpm dev
```

## Evaluation Philosophy
See `docs/philosophy.md` for how DebateBench treats judges as part of the evaluation environment and how to build skepticism-friendly evidence.

## Where to go next
- CLI details: `docs/cli-reference.md`
- Config schema and prompts: `docs/config-guide.md`
- Results schema: `docs/results-schema.md`
- Dashboard overview: `docs/dashboard.md`
- Dashboard ingestion (Next.js): `docs/dashboard-ingestion.md`
- Dashboard API: `docs/dashboard-api.md`
- Troubleshooting: `docs/troubleshooting.md`
- Dev workflow: `docs/dev-workflow.md`
