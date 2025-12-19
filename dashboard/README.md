# DebateBench Dashboard (Next.js)

Interactive, read-only dashboard that reads a private debates JSONL from S3 (via signed URL), computes derived metrics server-side, and renders preset + ad‑hoc charts (Vega-Lite).

## Setup

1) Copy `.env.example` to `.env` (or `.env.local`) and fill with your bucket/key and creds allowed to sign `GetObject`:

```
AWS_S3_BUCKET_NAME=debatebench-results
S3_BUCKET=debatebench-results  # fallback for older deploys
S3_REGION=us-east-1
S3_KEY=sample5/balanced-2025-11-30/results_sample5/debates_sample5-11-30-2025_balanced_sides.jsonl
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_URL_EXPIRY_SECONDS=900
# Set OPENROUTER_API_KEY to enable live pricing (snapshot used if unset)
OPENROUTER_API_KEY=...

# Optional: cache metrics API responses (ms); defaults to 300000 (5 minutes)
METRICS_CACHE_MS=300000
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

Open http://localhost:3000. The app calls `/api/metrics` (server parses + derives metrics from the signed JSONL) and hydrates the UI with pre-computed data; the client no longer parses the full debates file.

## What’s implemented
- Dark-mode layout with hero, tabbed highlights (Elo, win rate, tokens, cost), sticky category/model filter bar, discovery tiles, and (optional) compare drawer synced to URL. The compare UI (including pricing-table actions) is hidden by default; set `NEXT_PUBLIC_ENABLE_COMPARE=true` to surface it.
  - Filter semantics: single-category selection uses server-derived per-category aggregates. Multi-category selection merges per-category aggregates client-side (counts are exact; Elo/means are weighted approximations). Judge agreement/side-preference charts are not recomputed for filtered subsets; filters only drop visible rows/columns per selected models/categories.
- KPIs, Elo leaderboard, win-rate bars, side-bias bars, head-to-head heatmap, topic/category heatmap (category filter), judge agreement heatmap, Elo vs win-rate scatter, price-to-performance scatter (log USD/1M, Elo/Win-rate toggle with quadrant shading).
- Cost highlights summarize the full selected run (no “recent” window).
- Cost snapshot table (per‑1M tokens) with live pricing override when `OPENROUTER_API_KEY` is set; falls back to bundled snapshot otherwise.
- Custom chart builder: choose dataset (debates or judges), chart type (bar/scatter/heatmap/box), and fields for X/Y/Color to generate Vega-Lite charts. UI is hidden by default; set `NEXT_PUBLIC_ENABLE_BUILDER=true` to surface it.
- Server computes all derived metrics via `/api/metrics`; client only renders. Default caching uses an in-process TTL. Elo now mirrors the config in the debates JSONL (falls back to the embedded `elo.initial_rating`/`k_factor` if present).
- Pricing: live when `OPENROUTER_API_KEY` is set; otherwise snapshot bundled in `src/lib/pricing.ts`.

### Rate limiting
- Built-in, in-memory per-IP token bucket.
- Defaults: pricing 60 req/min; metrics 20 req/min.
- Override via env: `RL_PRICING_CAPACITY`, `RL_PRICING_REFILL_MS`, `RL_METRICS_CAPACITY`, `RL_METRICS_REFILL_MS`.

## Code structure (dashboard)
- `src/app/page.tsx`: orchestration—loads derived data from `/api/metrics`, wires hooks, renders modular sections.
- `src/hooks/`: `useHighlightsState`, `useCompareQuery` (URL-synced compare; gated by flag), `usePricingData`.
- `src/lib/specs/`: pure Vega specs (`core.ts`, `highlights.ts`); `src/lib/format.ts` for small formatters.
- `src/components/dashboard/`: layout pieces (Hero, FilterBar, DiscoveryTiles, HighlightLists, PricingTable, CompareDrawer).
- `src/lib/pricing.ts`: bundled snapshot + optional fetch helper (uses live data when `OPENROUTER_API_KEY` is configured).

## Adding more runs later
- Extend `/api/manifest` to return multiple keys and add a run selector in the UI.

## Optional live pricing
- Set `OPENROUTER_API_KEY` to enable live pricing; if unset, the dashboard falls back to the built-in snapshot in `src/lib/pricing.ts`.

## Deploy
- Set the same env vars on Vercel (or your host). Ensure the deploy role can sign `GetObject` on the configured key.
