# Dashboard Overview

What the Next.js dashboard shows, how it uses DebateBench outputs, and the
limits/privacy assumptions to keep in mind.

## What it shows
- Aggregate model performance (Elo, win rates, dimension averages).
- Judge agreement and side bias analysis.
- Token usage and cost summaries (observed costs preferred; pricing fallback).
- Optional charts and comparisons (feature flags controlled via env).

## Data sources
The dashboard is read-only and derives everything server-side from:
- `debates_<tag>.jsonl` uploaded to S3 (or compatible storage).
- Optional pricing data (live if `OPENROUTER_API_KEY` is set; otherwise snapshot).

## Performance expectations
- The server parses the JSONL to build aggregates on demand.
- Very large files can time out or exceed memory; keep runs to a few thousand
  debates unless you plan to scale the API.

## Privacy and data handling
- Debates can contain sensitive content. Treat the JSONL as private.
- The dashboard signs short-lived URLs and only allowlists configured keys.
- Avoid embedding secrets in the client; keep keys in env only.

## Related docs
- Ingestion/setup: `docs/dashboard-ingestion.md`
- API endpoints: `docs/dashboard-api.md`
- Results schema: `docs/results-schema.md`
