# Dashboard Ingestion (Next.js)

How to point the DebateBench dashboard at a new run produced by the CLI.

## What the dashboard expects
- A debates JSONL file (`results/debates_<tag>.jsonl`) uploaded somewhere reachable (typically S3).
- Optional: pricing data via `OPENROUTER_API_KEY` for live token costs; otherwise the bundled snapshot is used. When debates include observed costs (captured via OpenRouter `usage.include=true`), the dashboard prefers those over price tables.
- Cost highlights are “observed-or-nothing”: if any observed costs exist, the card shows only models with observed cost data (it will list fewer than Top N if some models lack usage costs) and will not blend in price-table entries for the missing models. Mixed datasets may therefore show shorter cost lists; this is intentional.
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
In `dashboard/.env` (or `.env.local` for local dev):
```
S3_BUCKET=my-results-bucket
S3_REGION=us-east-1
S3_KEY=demos/demo-jsonl/debates_demo.jsonl   # key to the uploaded JSONL
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_URL_EXPIRY_SECONDS=900                    # signed URL TTL
OPENROUTER_API_KEY=...                       # optional, enables live pricing fallback

# Optional rate limiting overrides
# RL_PRICING_CAPACITY=60
# RL_PRICING_REFILL_MS=60000
# RL_METRICS_CAPACITY=20
# RL_METRICS_REFILL_MS=60000
```

## Start the dashboard locally
```bash
cd dashboard
pnpm install
pnpm dev
# open http://localhost:3000
```

## Deploy
- Set the same env vars on your host (e.g., Vercel). Ensure the deploy IAM role can sign `GetObject` on the configured key.
- The API signs only allowlisted keys from env; bucket objects remain private.

## Mapping CLI outputs to the dashboard
- Primary input: `debates_<tag>.jsonl`.
- Derived metrics inside the dashboard include: Elo, win rates, side bias, head-to-head, judge agreement, topic/category splits, token usage, and cost snapshot.
- If you also upload `viz_<tag>/` and `plots_<tag>/`, you can expose them as download links in the UI, but they are not required for rendering.

## Updating to a new run
1) Upload the new debates file to S3.
2) Update `S3_KEY` (and optionally label) in the dashboard env.
3) Redeploy or restart the dev server.

## Common ingestion pitfalls
- Using a key that is not allowlisted by `S3_KEY`: the signer will reject it.
- Uploading an empty or partial debates file: the dashboard will show zeros; verify with `debatebench inspect-debate --latest` before uploading.
- Large files: the dashboard streams and parses JSONL client-side; ~3,000 debates (a few MB) is the assumed v1 limit.
