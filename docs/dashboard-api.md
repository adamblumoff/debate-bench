# Dashboard API Reference

Server-side endpoints used by the Next.js dashboard.

## `GET /api/manifest`
Returns metadata about available runs and the default run id.

Response (shape):
- `runs`: list of `{ id, label? }`
- `defaultRunId`: string

Notes:
- The manifest is generated from env and/or local metadata depending on deploy.

## `GET /api/metrics`
Builds derived metrics and summaries from the debates JSONL.

Query params:
- `run=<id>`: select a specific run (optional)
- `refresh=1`: bypass caches (optional)
- `bias=full`: include CV bias metrics (optional)

Response (shape):
- `derived`: aggregated metrics for the selected run
- `derivedByCategory`: per-category aggregates (if categories exist)
- `meta`: `{ debateCount, modelCount, categories }`
- `costSummary`: total cost/time summaries

Notes:
- This endpoint is the most expensive; it parses and aggregates JSONL.
- If `bias=full` is requested, additional CV data is computed.

## `GET /api/pricing`
Fetches or returns cached pricing data for models (optional).

Query params:
- `refresh=1`: force refresh (optional)

Notes:
- If `OPENROUTER_API_KEY` is missing, a bundled snapshot is used.
- Rate limiting is applied via env (`RL_*` vars).

## `POST /api/sign`
Signs a request for an allowlisted object key.

Body (shape):
- `key`: S3 object key

Response (shape):
- `url`: signed URL

Notes:
- Only allowlisted keys are signed.

## `GET /api/debates`
Returns the raw debates JSONL if allowlisted.

Query params:
- `run=<id>`: select a run

Notes:
- Access is gated by the same allowlist as `/api/sign`.
