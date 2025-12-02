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
- Dark-mode layout with hero, tabbed highlights (Elo, win rate, tokens, cost), sticky filter bar (Top N + category), discovery tiles, and shareable compare drawer (state synced to URL).
- KPIs, Elo leaderboard, win-rate bars, side-bias bars, head-to-head heatmap, topic/category heatmap (category filter), judge agreement heatmap, Elo vs win-rate scatter.
- Cost snapshot table (per‑1M tokens) with optional live pricing override.
- Custom chart builder: choose dataset (debates or judges), chart type (bar/scatter/heatmap/box), and fields for X/Y/Color to generate Vega-Lite charts.

## Code structure (dashboard)
- `src/app/page.tsx`: light orchestration—loads data, wires hooks, renders modular sections.
- `src/hooks/`: `useHighlightsState`, `useCompareQuery` (URL-synced compare), `usePricingData`.
- `src/lib/specs/`: pure Vega specs (`core.ts`, `highlights.ts`); `src/lib/format.ts` for small formatters.
- `src/components/dashboard/`: layout pieces (Hero, FilterBar, DiscoveryTiles, HighlightLists, PricingTable, CompareDrawer).
- `src/lib/pricing.ts`: bundled snapshot + optional fetch helper.

## Adding more runs later
- Extend `/api/manifest` to return multiple keys and add a run selector in the UI.

## Optional live pricing
- Set `NEXT_PUBLIC_PRICING_URL` to a JSON endpoint matching `{ updated, currency, rows: [{ model_id, provider, input_per_million, output_per_million }] }`.
- If unset or fetch fails, the dashboard falls back to the built-in snapshot in `src/lib/pricing.ts`.

## Deploy
- Set the same env vars on Vercel (or your host). Ensure the deploy role can sign `GetObject` on the configured key.
