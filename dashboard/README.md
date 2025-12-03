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
# Optional: gate live OpenRouter pricing; snapshot is always available
PRICING_GATE_TOKEN=dev-local-token

# Set OPENROUTER_API_KEY only when you want live pricing and the caller supplies the gate token
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
- Dark-mode layout with hero, tabbed highlights (Elo, win rate, tokens, cost), sticky filter bar (Top N + category), discovery tiles, and shareable compare drawer (state synced to URL).
- KPIs, Elo leaderboard, win-rate bars, side-bias bars, head-to-head heatmap, topic/category heatmap (category filter), judge agreement heatmap, Elo vs win-rate scatter.
- Cost snapshot table (per‑1M tokens) with optional live pricing override (gated by `PRICING_GATE_TOKEN`).
- Custom chart builder: choose dataset (debates or judges), chart type (bar/scatter/heatmap/box), and fields for X/Y/Color to generate Vega-Lite charts.
- Server computes all derived metrics via `/api/metrics`; client only renders. Default caching uses an in-process TTL.

## Code structure (dashboard)
- `src/app/page.tsx`: orchestration—loads derived data from `/api/metrics`, wires hooks, renders modular sections.
- `src/hooks/`: `useHighlightsState`, `useCompareQuery` (URL-synced compare), `usePricingData`.
- `src/lib/specs/`: pure Vega specs (`core.ts`, `highlights.ts`); `src/lib/format.ts` for small formatters.
- `src/components/dashboard/`: layout pieces (Hero, FilterBar, DiscoveryTiles, HighlightLists, PricingTable, CompareDrawer).
- `src/lib/pricing.ts`: bundled snapshot + optional fetch helper.

## Adding more runs later
- Extend `/api/manifest` to return multiple keys and add a run selector in the UI.

## Optional live pricing
- `PRICING_GATE_TOKEN` gates the live OpenRouter call. The client must send header `x-pricing-token: <PRICING_GATE_TOKEN>`; otherwise `/api/pricing` always returns the bundled snapshot.
- Set `OPENROUTER_API_KEY` only when you intend to allow live pricing.
- If unset or a gate token is missing/invalid, the dashboard falls back to the built-in snapshot in `src/lib/pricing.ts`.

## Deploy
- Set the same env vars on Vercel (or your host). Ensure the deploy role can sign `GetObject` on the configured key.
