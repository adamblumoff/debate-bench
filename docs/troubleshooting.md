# Troubleshooting & FAQ

Quick fixes for common issues when running DebateBench.

## Setup / Auth
- **Missing OPENROUTER_API_KEY**: Set it in `.env`, then re-run. Interactive selection and any real completions require it.
- **403/401 from OpenRouter**: Ensure the key is valid for the selected models; some providers restrict access.
- **Proxy/SSL errors**: Set `HTTP_PROXY`/`HTTPS_PROXY` if needed; check local TLS interception tools.

## Model selection & probing
- **“No text-based OpenRouter models found”**: Increase `--openrouter-months` or disable interactive selection (`--no-openrouter-select`) and provide `configs/models.yaml`.
- **Probe drops models**: `--openrouter-probe` sends a 1-token request and removes failures. To keep them, run with `--no-openrouter-probe` (may fail later).

## Judges & panels
- **“Need at least N judges after exclusions”**: When using `--judges-from-selection`, active debaters are excluded from the judge pool. Add more models or turn off that flag.
- **Unbalanced judge usage**: Use default `--balanced-judges` to even usage by topic/pair; `--random-judges` is uniform sampling.
- **Judge JSON parse failures**: Enable `--log-failed-judges` to capture raw replies in `results/run_<tag>/failed_judges.jsonl`. Judges are retried with alternates until the expected count is reached; if not, the debate fails.

## Debate execution
- **Empty turn / banned model**: If a model returns empty content after retries, the run fails unless `--skip-on-empty` is set, which bans that model for the remainder. Check `progress.json` for `banned_models`.
- **Long or runaway turns**: Tighten per-round `max_tokens` in `configs/config.yaml`, or run with `--apply-stage-token-limits --openrouter-max-tokens <N>`. (Note: `--openrouter-max-tokens` alone does not override `configs/config.yaml` stage caps.)
- **High variance outputs**: Lower `--openrouter-temperature` (debater) or use deterministic models. Judges are already forced to temperature 0.
- **429s or rate limiting**: The OpenRouter adapter backs off automatically (respects `Retry-After` when provided). The live view shows backoff seconds and reason; repeated 429s usually mean too much concurrency for the account tier.
- **Free models feel slow**: If any model id ends with `:free`, the runner throttles to ~20 RPM to avoid OpenRouter rate-limit churn.

## Cost / time
- **Costs look too high**: Use `--dry-run` to see per-model/per-judge estimates; lower `--debates-per-pair`, use fewer topics (`--sample-topics`), or cap tokens.
- **Time estimates missing**: `--estimate-time` uses timing snapshots (`results/run_<tag>/timing_snapshot.json`) when available. If none exist, it falls back to recent debate medians or a heuristic; create a small run first.
- **Estimates feel off**: Time and cost estimates are best-effort and can be inaccurate today; we plan to improve both.

## Resume / append
- **Resume skipped everything**: Ensure `--run-tag` matches the debates file you expect, and that `--debates-per-pair` matches the original plan.
- **Incremental append errors**: Confirm `results/run_<tag>/config_snapshot/cli_args.json` and `effective_selection.json` exist, and that the new model ID is present in `configs/models.yaml`.

## CLI UX
- **Curses wizard not available**: The CLI falls back to prompt-based selection. You can also disable it with `--no-tui-wizard`.
- **Terminal colors garbled**: Rich output uses ANSI colors; set `TERM=xterm-256color` or run with `NO_COLOR=1` to disable colors.
- **Live view flicker**: Refresh is throttled, but on slow terminals you can disable Rich color via `NO_COLOR=1` to reduce redraw cost.

## Plotting
- **Matplotlib/Qt errors**: Backend is non-interactive; ensure you have headless-friendly packages (installed via project deps). If missing system libs, regenerate plots on a machine with the deps.

## Environment
- **.env not loaded**: DebateBench calls `dotenv.load_dotenv()` in `settings.py`. Make sure `.env` is in repo root (or set env vars directly).

## When in doubt
1) Re-run with `--dry-run` to validate selection and costs.
2) Check `results/run_<tag>/progress.json` for state, banned models, counts.
3) Inspect `failed_judges.jsonl` (if enabled) to see parsing failures.
4) Reduce scope: fewer topics, lower debates per pair, tighter token caps.
