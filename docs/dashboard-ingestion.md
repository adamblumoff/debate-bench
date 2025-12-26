# Dashboard Ingestion (Next.js)

How to point the DebateBench dashboard at a new run produced by the CLI.

## What the dashboard expects
- A debates JSONL file (`results/debates_<tag>.jsonl`) uploaded somewhere reachable (typically S3).
- Optional: pricing data via `OPENROUTER_API_KEY` for live token costs; otherwise the bundled snapshot is used. When debates include observed costs (captured via OpenRouter `usage.include=true`), the dashboard prefers those over price tables.
- Cost highlights are “observed-or-nothing”: if any observed costs exist, the card shows only models with observed cost data (it will list fewer than Top N if some models lack usage costs) and will not blend in price-table entries for the missing models. Mixed datasets may therefore show shorter cost lists; this is intentional.
- Cost summary panels aggregate across the full selected run (not just the most recent debates).
- The dashboard server derives all metrics; CSVs/PNGs from `viz_*/plots_*` are not required but can be offered as downloads.

## Upload the debates file
```bash
# Upload only the debates file
debatebench upload-results \
  --source results/debates_demo.jsonl \
  --bucket my-results-bucket \
  --prefix demos/demo-jsonl

# Or upload the whole run directory for reference
debatebench upload-results \
  --source results/run_demo \
  --bucket my-results-bucket \
  --prefix runs/demo
```

## Configure the dashboard (Next.js app)
In `dashboard/.env`:
```
AWS_S3_BUCKET_NAME=my-results-bucket
S3_BUCKET=my-results-bucket                  # fallback for older deploys
S3_REGION=us-east-1
S3_KEY=demos/demo-jsonl/debates_demo.jsonl   # key to the uploaded JSONL
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_ENDPOINT=https://storage.railway.app      # optional: Railway / other S3-compatible endpoint
S3_FORCE_PATH_STYLE=true                     # recommended for Railway
S3_URL_EXPIRY_SECONDS=900                    # signed URL TTL
OPENROUTER_API_KEY=...                       # optional, enables live pricing fallback

# Optional rate limiting overrides
# RL_PRICING_CAPACITY=60
# RL_PRICING_REFILL_MS=60000
# RL_METRICS_CAPACITY=20
# RL_METRICS_REFILL_MS=60000
```

## Optional CLI postupload defaults
If you want `debatebench run --postupload` to work without extra flags, set any of:
```
DEBATEBENCH_S3_BUCKET=debatebench-results   # default if omitted
DEBATEBENCH_S3_PREFIX=runs                 # base prefix; per-run default is runs/<run_tag>
DEBATEBENCH_AWS_PROFILE=debatebench-uploader
DEBATEBENCH_S3_REGION=us-east-1
DEBATEBENCH_S3_ENDPOINT=https://<railway-bucket-endpoint>   # for Railway buckets or other S3-compatible storage
DEBATEBENCH_S3_FORCE_PATH_STYLE=true                        # recommended for Railway (path-style)
```
The CLI also falls back to `S3_BUCKET`, `S3_PREFIX`, `AWS_PROFILE`, and `S3_REGION` if present.

## Mapping CLI outputs to the dashboard
- Primary input: `debates_<tag>.jsonl`.
- Derived metrics inside the dashboard include: Elo, win rates, side bias, head-to-head, judge agreement, topic/category splits, token usage, and cost snapshot.
- If you also upload `viz_<tag>/` and `plots_<tag>/`, you can expose them as download links in the UI, but they are not required for rendering.

## Updating to a new run
1) Upload the new debates file to S3.
2) Update `S3_KEY` (and optionally label) in the dashboard env. Bucket comes from `AWS_S3_BUCKET_NAME`.
3) Redeploy or restart the dev server.

## Common ingestion pitfalls
- Using a key that is not allowlisted by `S3_KEY`: the signer will reject it.
- Uploading an empty or partial debates file: the dashboard will show zeros; verify with `debatebench inspect-debate --latest` before uploading.
- Large files: the dashboard parses JSONL server-side to build aggregates; ~3,000 debates (a few MB) is the assumed v1 limit.

## Related docs
- Overview: `docs/dashboard.md`
- API endpoints: `docs/dashboard-api.md`
- Local dev workflow: `docs/dev-workflow.md`
