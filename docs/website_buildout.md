# Interactive DebateBench Dashboard (Next.js)

This document started as a buildout plan; the current dashboard implementation has evolved. For day-to-day usage and env setup, prefer `dashboard/README.md` and `docs/dashboard-ingestion.md`.

## Current architecture (as implemented)
- The dashboard is read-only and loads a private debates JSONL from S3 via a short-lived signed URL.
- Parsing + metric derivation happens server-side in `/api/metrics` (Node.js runtime). The client primarily renders derived tables and charts.
- Run selection is exposed via `/api/manifest` (single run by default; can be extended to multi-run).
- `/api/sign` issues allowlisted signed URLs; `/api/debates` can serve the raw JSONL behind the same allowlist.
- Live pricing is optional: if `OPENROUTER_API_KEY` is set, `/api/pricing` can refresh pricing; otherwise the UI falls back to a bundled snapshot.

## Environment variables (dashboard)
In `dashboard/.env` (or `.env.local` if you prefer Next’s defaults):
```
AWS_S3_BUCKET_NAME=debatebench-results
S3_BUCKET=debatebench-results               # fallback for older deploys
S3_REGION=us-east-1
S3_KEY=runs/demo/debates_demo.jsonl         # key to the uploaded JSONL
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_ENDPOINT=https://storage.railway.app     # optional: Railway / other S3-compatible endpoint
S3_FORCE_PATH_STYLE=true                    # recommended for Railway
S3_URL_EXPIRY_SECONDS=900
OPENROUTER_API_KEY=...                      # optional: enables live pricing fallback
```

## Data model (from JSONL)
Each line is a `DebateRecord` containing:
- `transcript` (topic, pro/con model IDs, turns including timing/token/cost fields when available)
- `judges` (per-judge winner + per-dimension scores)
- `aggregate` (panel winner + mean scores per dimension)

## Notes
- Size limits: the server parses the JSONL to build aggregates; extremely large runs can time out or exceed memory limits.
- Security: signing endpoints allowlist the configured key(s) from env; bucket objects remain private.
