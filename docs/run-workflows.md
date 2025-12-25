# Run Workflows (Recipes)

Practical, end-to-end examples for common scenarios. All commands assume repo root as CWD.

## 1) Fully interactive run (default)
Goal: pick topics/models/judges via the curses wizard, run balanced debates, generate summaries/plots/ratings.
```bash
debatebench init                    # once per repo/venv
debatebench run --debates-per-pair 1 --sample-topics 5 --run-tag demo
```
What happens:
- Wizard asks for topics, debaters, judges (text-only OpenRouter models from last 4 months).
- Each model is probed with a 1-token request; failures are dropped.
- Balanced sides (A vs B and B vs A) and balanced judges.
- Live view shows concurrent debates, per-debate round progress, judging status, retries, and rate-limit/backoff info.
- Outputs: `results/debates_demo.jsonl`, `results/viz_demo/`, `results/plots_demo/`, `results/ratings_demo.json`, `results/run_demo/*`.

## 2) Scripted run (no prompts)
Goal: use static configs and avoid any interactive selection.
```bash
debatebench run \
  --no-tui-wizard --no-topic-select --no-openrouter-select \
  --models-path configs/models.yaml \
  --judges-path configs/judges.yaml \
  --topics-path configs/topics.json \
  --debates-per-pair 2 \
  --run-tag batch1
```
Notes:
- Topics/models/judges come directly from config files.
- Keep `--openrouter-probe` on (default) to drop unusable entries.
- Alternatively, use `--prod-run` to force config-only selection with balanced judges and judges-from-selection.

## 3) Cheap smoke test (minutes, low cost)
Use predefined light models from `configs/quick-test-models.yaml` (random topic(s), debates-per-pair=1, balanced sides ON by default).
```bash
debatebench run --quick-test --run-tag smoke
```
Runs random topic(s) (honors `--sample-topics`), fixed debater pair, 3 judges, with both orientations (pro/con swapped) because `--balanced-sides` remains on by default. Postrun summaries/plots and postupload are skipped in quick-test mode.

## 4) Judge-only sanity test
Focus on judge JSON compliance with a tiny match.
```bash
debatebench run --judges-test --run-tag judges-smoke
```
Single debate, fixed debaters (Haiku vs Gemini 2.5 Flash Lite), 2 judges.

## 5) Resume an interrupted run
If the debates file already contains partial results:
```bash
debatebench run --resume --run-tag demo
```
Planner skips completed topic/pair/rep combos based on `results/debates_demo.jsonl`.

## 6) Incremental append: add one new model to an existing run
Prereqs: existing run tag `demo`, files `results/debates_demo.jsonl` and `results/run_demo/config_snapshot/{cli_args.json,effective_selection.json}` present; new model exists in `configs/models.yaml`.
```bash
debatebench run --new-model openai-gpt-5-mini --run-tag demo --dry-run   # preview schedule/cost
debatebench run --new-model openai-gpt-5-mini --run-tag demo             # execute append
```
Planner infers topics, debates-per-pair, judge settings, and only schedules pairs involving the new model.

## 7) Cost and time planning without running
```bash
debatebench run --run-tag plan --debates-per-pair 1 --sample-topics 4 --dry-run
```
Outputs:
- Console: estimated wall time from timing snapshots (p50/p75/p90 with buffer) or recent medians, rough USD cost (live OpenRouter pricing + optional activity snapshot), per-model/per-judge cost share. Both time and cost estimates are rough and may be inaccurate; we plan to improve them. During actual runs, observed OpenRouter costs are recorded per turn/judge when provided and override snapshots in the dashboard.
- File: `results/run_plan/dryrun_schedule.json` with every planned debate and judge panel.

## 8) Tighten or loosen token caps
- Cap all stages to 768 tokens (works in all modes) and judges to 256 when selecting judges from OpenRouter/quick-test (otherwise set caps in `configs/judges.yaml`):
  ```bash
  debatebench run --apply-stage-token-limits --openrouter-max-tokens 768 --openrouter-judge-max-tokens 256
  ```
- Keep the existing per-round caps from `configs/config.yaml` but cap judge outputs when selecting judges from OpenRouter:
  ```bash
  debatebench run --openrouter-judge-max-tokens 400
  ```

## 9) Upload artifacts to S3-compatible storage (AWS or Railway)
After a run, push the results directory tree. If you’ve set `DEBATEBENCH_S3_BUCKET`/`DEBATEBENCH_S3_ENDPOINT` (or the `S3_*` equivalents), you don’t need to pass a bucket:
```bash
debatebench upload-results --source results/run_demo --prefix runs/demo
```
Add `--dry-run` to preview keys. For Railway buckets, ensure `DEBATEBENCH_S3_ENDPOINT` is set and path-style is enabled (`DEBATEBENCH_S3_FORCE_PATH_STYLE=true`), or pass `--endpoint-url` / `--force-path-style`.

Note: `debatebench run` defaults `--postupload` on and `--postupload-include-artifacts` off. Use `--no-postupload` to skip uploads for a specific run.

## 10) Inspect and share outputs
- Show leaderboard:
  ```bash
  debatebench show-leaderboard --ratings-path results/ratings_demo.json --top 10
  ```
- Inspect the latest debate:
  ```bash
  debatebench inspect-debate --latest
  ```
- Regenerate summaries/plots from an existing debates file:
  ```bash
  debatebench summarize --debates-path results/debates_demo.jsonl --out-dir results/viz_demo
  debatebench plot --viz-dir results/viz_demo --out-dir results/plots_demo
  ```
