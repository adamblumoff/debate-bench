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
      max_tokens: null   # null = uncapped unless CLI caps are applied
    - role: con
      stage: opening
      max_tokens: null
    - role: pro
      stage: rebuttal
      max_tokens: null
    - role: con
      stage: rebuttal
      max_tokens: null
    - role: pro
      stage: closing
      max_tokens: null
    - role: con
      stage: closing
      max_tokens: null
  temperature: 0.7        # default debater temperature (overridable via CLI)
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
  min_games_for_display: 5
```

Notes:
- Rounds: list in speaking order. `role` is `pro`/`con`; `stage` is free text (used in prompts and CSVs). `max_tokens` can be overridden by `--apply-stage-token-limits` + `--openrouter-max-tokens`.
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
    token_limit: null          # per-turn cap; null = uncapped unless overridden
    endpoint: null             # override OpenRouter endpoint if needed
    parameters:
      temperature: 0.7
      # optional: timeout, retries, backoff, max_tokens
```
Rules:
- `provider` must be `openrouter` for built-in adapters.
- `id` is the internal handle used in outputs; avoid slashes/spaces (the interactive picker auto-normalizes to dash).
- If you leave `token_limit` null, the CLI may still cap via `--openrouter-max-tokens` or stage limits.
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
      temperature: 0.0   # forced to 0.0 in code for determinism
```
Rules:
- Judge IDs must not collide with debater IDs.
- If `--judges-from-selection` is used, these are ignored and the debater list is reused (active debaters are excluded from the sample for each debate).
- `openrouter_judge_max_tokens` CLI flag can cap judge outputs regardless of `token_limit`.

---

## `quick-test-models.yaml`
Used by `debatebench run --quick-test` to provide a tiny, cheap smoke test.
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
1) If `--apply-stage-token-limits` is passed, every stage uses `--openrouter-max-tokens`.
2) Else, per-round `max_tokens` from `config.yaml` apply. When `max_tokens` is null, the parser defaults it to 5,000.
3) Else, the adapter uses model `token_limit` or `parameters.max_tokens` if provided.
4) If none apply, the adapter defaults to 1,024.

Judge caps: `--openrouter-judge-max-tokens` overrides judge `token_limit`/`parameters.max_tokens`; otherwise those apply; otherwise provider defaults.

---

## Adding new providers
Currently only `provider: openrouter` is supported by `debatebench.models`. To add another provider, implement an adapter in `models.py` and expose it via `build_debater_adapter` / `build_judge_adapter`; mirror the config shape shown above.
