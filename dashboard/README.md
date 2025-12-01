# DebateBench Dashboard (Next.js)

Interactive, read-only dashboard that streams a private debates JSONL from S3 (via signed URL), builds derived tables client-side, and renders preset + ad‑hoc charts (Vega-Lite).

## Setup

1) Copy `.env.example` to `.env.local` and fill with your bucket/key and AWS creds allowed to sign `GetObject`:

```
S3_BUCKET=debatebench-results
S3_REGION=us-east-1
S3_KEY=sample5/balanced-2025-11-30/results_sample5/debates_sample5-11-30-2025_balanced_sides.jsonl
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_URL_EXPIRY_SECONDS=900
```

2) Install deps (pnpm):

```
pnpm install
# if your global pnpm store has permission issues, reuse repo-local paths
PNPM_HOME=../.pnpm-home PNPM_STORE_PATH=../.pnpm-store pnpm install
```

3) Run dev server:

```
pnpm dev
```

Open http://localhost:3000. The app calls `/api/manifest` → `/api/sign` to fetch a signed URL, streams the JSONL, and computes metrics on the client.

## What’s implemented
- Overview with KPIs, leaderboard, side-bias bars, head-to-head heatmap, topic/category heatmap, judge agreement heatmap.
- Custom chart builder: choose dataset (debates or judges), chart type (bar/scatter/heatmap/box), and fields for X/Y/Color to generate Vega-Lite charts.

## Adding more runs later
- Extend `/api/manifest` to return multiple keys and add a run selector in the UI.

## Deploy
- Set the same env vars on Vercel (or your host). Ensure the deploy role can sign `GetObject` on the configured key.
