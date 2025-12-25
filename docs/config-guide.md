# Config Guide

How DebateBench reads configuration files and how to author them safely. All paths are relative to the repo root unless otherwise noted.

## Files
- `configs/config.yaml` — benchmark + debate + scoring + Elo settings.
- `configs/topics.json` — list of topics `{id, motion, category?}`.
- `configs/models.yaml` — debater model entries.
- `configs/judges.yaml` — judge model entries (IDs must not overlap with debaters).
- `configs/quick-test-models.yaml` — presets for `--quick-test`.

---

## `config.yaml` schema (nested style)
```yaml
benchmark:
  name: "DebateBench"
  version: "v0.1"

debate:
  language: "en"
  rounds:
    - role: pro
      stage: opening
      max_tokens: 4096   # if null, the parser treats it as 5000 (not uncapped)
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
  system_prompt_pro: |    # see default text in repo
  system_prompt_con: |

scoring:
  dimensions:
    persuasiveness: {min: 1, max: 10, description: "..."}
    reasoning:      {min: 1, max: 10, description: "..."}
    factuality:     {min: 1, max: 10, description: "..."}
    clarity:        {min: 1, max: 10, description: "..."}
    safety:         {min: 1, max: 10, description: "..."}
  judges_per_debate: 3
  judge_system_prompt: |  # JSON-only scoring instructions (winner derived later)

elo:
  initial_rating: 400
  k_factor: 32
```

Notes:
- Rounds: list in speaking order. `role` is `pro`/`con`; `stage` is free text (used in prompts and CSVs). `max_tokens: null` is treated as 5,000 by the config parser. `--apply-stage-token-limits` can overwrite opening/rebuttal/closing token limits to `--openrouter-max-tokens` for a run.
- Languages: optional per-round `language` can be set; defaults to `debate.language`.
- Prompts: the shipped system prompts already include turn guidance, safety reminders, and `<END_OF_TURN>` requirement.
- Scoring dimensions: ids should be short, lowercase-friendly; min/max define the integer range judges must return. Winner is computed from mean scores (no winner field required).
- Judge prompt: keep JSON-only; rationale is discarded and may cause drops.
- Legacy flat schema is still accepted (`benchmark_version`, `rounds`, `scoring`, etc.); it is normalized internally to the same shape.

---

## `topics.json`
Array of topics:
```json
[
  {"id": "t001", "motion": "Governments should ...", "category": "privacy"},
  ...
]
```
Notes:
- `id` should be stable across runs; `category` is optional and used in some plots.
- Interactive selection (`--topic-select`) starts with all topics disabled; you toggle ones to include.
- `--sample-topics N` randomly samples after selection.

---

## `models.yaml` (debaters)
Shape (list or `models:` key):
```yaml
models:
  - id: openai-gpt-5.1
    provider: openrouter
    model: openai/gpt-5.1
    token_limit: null          # used only if a round token limit is unset; debate rounds normally pass max_tokens from config.yaml
    endpoint: null             # override OpenRouter endpoint if needed
    parameters:
      temperature: 0.7
      # optional: timeout, retries, backoff, max_tokens
```
Rules:
- `provider` must be `openrouter` for built-in adapters.
- `id` is the internal handle used in outputs; avoid slashes/spaces (the interactive picker auto-normalizes to dash).
- Debate turn length is primarily controlled by per-round `max_tokens`/`token_limit` in `configs/config.yaml`. `token_limit` in `models.yaml` only matters if a round token limit ends up unset (or for future providers).
- Additional OpenRouter request params can be placed in `parameters` (e.g., `timeout`, `retries`, `backoff`).

---

## `judges.yaml`
Shape mirrors debaters plus `prompt_style` (unused today but reserved):
```yaml
judges:
  - id: anthropic-claude-sonnet-4.5
    provider: openrouter
    model: anthropic/claude-sonnet-4.5
    token_limit: null
    prompt_style: default
    parameters:
      temperature: 0.0   # forced to 0.0 in code for determinism (ignored if set)
```
Rules:
- Judge IDs must not collide with debater IDs.
- If `--judges-from-selection` is used, these are ignored and the debater list is reused (active debaters are excluded from the sample for each debate).
- When selecting judges from OpenRouter (`--openrouter-select`) or using `--quick-test`, `--openrouter-judge-max-tokens` assigns a token cap for judges. If you run with `--no-openrouter-select`, set `token_limit` / `parameters.max_tokens` in `configs/judges.yaml` instead.

---

## `quick-test-models.yaml`
Used by `debatebench run --quick-test` to provide a tiny, cheap smoke test (random topic(s), fixed debaters/judges).
```yaml
num_judges: 3
debaters: [...]
judges: [...]
```
Keep model IDs valid in your OpenRouter account; temperatures are usually lower to stabilize outputs.

---

## Prompt expectations (summary)
- Debater prompts: side-anchored, stage-aware, ask for 2–4 short paragraphs, discourage meta/planning, and require `<END_OF_TURN>`. Thinking tags (`<thinking>...</thinking>` or ```thinking fences) are stripped before judging.
- Judge prompt: JSON-only, no winner field, integer scores per dimension. Replies are validated against a strict JSON schema; all-minimum-score replies are rejected; non-JSON fallbacks are parsed best-effort and may be dropped.

---

## Token limits: how precedence works
Debaters:
1) The CLI passes the per-round `max_tokens`/`token_limit` from `configs/config.yaml` as `max_tokens` on each turn request.
2) If `--apply-stage-token-limits` is set, opening/rebuttal/closing rounds are overwritten to `--openrouter-max-tokens` for that run.
3) If a round token limit is ever unset/`None` (unusual), the OpenRouter adapter falls back to the model `token_limit`, then `parameters.max_tokens`, then 1,024.

Judges:
1) If a judge `token_limit` or `parameters.max_tokens` is set (via `configs/judges.yaml`, OpenRouter selection, or `--openrouter-judge-max-tokens` in quick/interactive modes), it is passed as `max_tokens`.
2) Otherwise, the request omits `max_tokens` and the provider default applies.

---

## Adding new providers
Currently only `provider: openrouter` is supported by `debatebench.models`. To add another provider, implement an adapter in `models.py` and expose it via `build_debater_adapter` / `build_judge_adapter`; mirror the config shape shown above.
