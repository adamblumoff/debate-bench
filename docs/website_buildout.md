# Interactive DebateBench Dashboard (Next.js)

## Goal & Scope
Public, read-only dashboard that loads one private debates JSONL from S3, visualizes key metrics, and offers an interactive chart builder where users choose X/Y fields (and color/group) to generate custom charts.

## Assumptions (fixed for v1)
- Single run/file at launch; no multi-run switching yet.
- S3-compatible bucket region: default `us-east-1` (or Railway `auto`).
- Max dataset size ~3,000 debates (JSONL stays a few MB); in-browser parsing is acceptable.
- Bucket is private; all access via short-lived signed GET URLs.
- No authentication; public read-only UI.

## Stack
- **Next.js (App Router)** + TypeScript.
- **AWS SDK v3** in API routes for signing S3 GETs.
- **react-vega** (Vega-Lite) for charts, including the custom builder.
- **Zustand + SWR** for client state and data fetch/cache.
- **Streaming JSONL parsing** in a Web Worker (line-by-line) for responsiveness.
- Styling: Tailwind (or similar utility layer) for fast layout.

## Environment Variables
```
AWS_S3_BUCKET_NAME=debatebench-results
S3_BUCKET=debatebench-results               # fallback for older deploys
S3_REGION=us-east-1
S3_KEY=sample5/balanced-2025-11-30/results_sample5/debates_sample5-11-30-2025_balanced_sides.jsonl
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_ENDPOINT=https://storage.railway.app     # optional: Railway / other S3-compatible endpoint
S3_FORCE_PATH_STYLE=true                    # recommended for Railway
``` 
(`S3_KEY` may later become a comma-list manifest when we add multi-run support.)

## Data Model (from JSONL)
Each line contains: `transcript` (pro/con model IDs, topic id/category, turns with timing/tokens), `aggregate` (winner, mean_pro/mean_con scores per dimension), `judges` (per-judge winner + scores), `created_at`.
Derived tables to compute client-side: overall winrates, side bias, head-to-head matrix, per-dimension averages, judge agreement, topic/category winrates, token/time stats.

## API Routes
- `GET /api/sign?key=S3_KEY` → returns short-lived signed URL for the configured JSONL (allowlist keys only).
- `GET /api/manifest` → returns the single configured run (id, label, s3_key). Future: multiple entries.
- (Optional later) `POST /api/filter` for server-side prefilter if files grow.

## Client Data Flow
1) Fetch manifest → request signed URL for the JSONL.
2) Stream-fetch JSONL; parse incrementally in a Web Worker; accumulate rows in memory (arrays or Arrow table) with progress indicator.
3) Build derived datasets (winrates, head-to-head, judge stats, topic/category tables).
4) Feed derived tables to canned charts and the custom Vega-Lite builder.

## Pages / UX
- **Overview**: KPI cards (top ratings, largest side gap, judge agreement range), rating bar, head-to-head heatmap.
- **Models**: select model(s); show rating, side bias bars, per-dimension averages, volatility.
- **Judges**: agreement heatmap, majority alignment bar, latency distribution.
- **Topics**: topic/category winrates, filter by model.
- **Builder** (interactive): choose dataset (debates, debate-aggregates, judge rows), pick X/Y, Color/Group, aggregation, chart type (bar/line/scatter/heatmap/box). Live Vega-Lite preview; export PNG/JSON spec; shareable URL params.
- **Data**: download links to the source JSONL and client-derived CSVs.

## Performance
- Stream + worker to avoid main-thread jank; show progress while loading.
- Cache parsed result in memory; optionally persist a lightweight snapshot keyed by ETag in `localStorage`.
- Lazy-load heavy deps (`react-vega`, `apache-arrow` if used).

## Security
- No auth; API signs only allowlisted keys from env to prevent arbitrary bucket reads.
- Short-lived signed URLs; no write routes.
- CORS limited to app origin.

## Deployment
- Host on Vercel (or similar). Provide env vars above. Ensure IAM creds allow `s3:GetObject` on the configured key for signing.

## Milestones
1) Scaffold Next.js app, env handling, and signer API route.
2) Implement streaming JSONL loader + worker; in-memory derived tables.
3) Ship Overview, Models, Judges, Topics pages with canned charts.
4) Build custom chart builder (X/Y/Color selectable, chart type, aggregation, export).
5) Polish UI, add data download page, and finalize deployment config.

## Future (after v1)
- Multi-run manifest & selector; compare runs side-by-side.
- Precompute Arrow/Parquet server-side for larger files.
- Optional auth (if bucket exposure policies change).
