# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pnpm dev          # Start Next.js dev server (localhost:3000)
pnpm build        # Production build
pnpm lint         # ESLint (next/core-web-vitals + typescript)
pnpm format       # ESLint --fix + Prettier
```

No test framework is configured. There are no test files.

## Architecture

Next.js 16 App Router dashboard that reads debate JSONL from S3, computes metrics server-side, and renders charts with Vega-Lite. All metrics are judge-driven and preference-based; Elo and win rates are aggregates, not ground-truth accuracy.

### Data flow

1. **S3 → Server**: `/api/metrics` fetches JSONL from S3 via signed URLs, parses it, and computes all derived metrics (`buildDerived` in `src/lib/metrics/buildDerived.ts`). Results are cached in-memory (5 min TTL).
2. **Server → Client**: Zustand store (`src/store/useDataStore.ts`) fetches `/api/metrics` via SWR. States: idle → loading → ready/error.
3. **Client rendering**: `src/app/page.tsx` orchestrates everything — builds chart specs from derived data, applies category/model filters, renders modular dashboard sections.

### Key modules

- **`src/lib/metrics/buildDerived.ts`** — Core computation: Elo ratings, win rates, head-to-head, topic/category stats, judge agreement, judge bias (logistic regression with ridge penalty + 5-fold CV), dimension scores, token/cost stats.
- **`src/lib/specs/`** — Pure functions that produce Vega-Lite specs. `highlights.ts` for highlight charts, `core.ts` for analysis charts.
- **`src/lib/highlights/filters.ts`** — Category/model filtering. Single-category uses exact server-computed per-category aggregates; multi-category merges client-side (weighted approximations for Elo/means).
- **`src/lib/vegaTheme.ts`** — Vega chart color constants (`TEXT`, `MUTED`, `BORDER`) and color range arrays (`accentRange`, `heatRange`, `divergingRange`). All chart specs apply `withVizTheme()`.

### API routes

| Route | Purpose |
|---|---|
| `/api/manifest` | Available runs (S3 keys). Rate limit: 30/min |
| `/api/metrics` | Main data endpoint. Params: `run`, `refresh`, `full`, `bias`. Rate limit: 20/min |
| `/api/pricing` | Live pricing from OpenRouter (falls back to snapshot). Rate limit: 60/min |
| `/api/sign` | Pre-signed S3 download URLs |
| `/api/debates` | Raw debate records for chart builder |

### Theming

- **CSS variables** in `src/app/globals.css` `:root` block define the full palette (`--bg-base`, `--card`, `--border`, `--accent`, etc.), radius, shadows, and z-index layers.
- **`@theme inline`** block maps CSS vars to Tailwind 4 tokens.
- **Fonts** loaded via `next/font/google` in `src/app/layout.tsx` (Geist Sans, Geist Mono, Space Grotesk).
- TSX components also use **hardcoded Tailwind classes** (`text-slate-*`, `bg-slate-*`) — these must be updated alongside CSS vars when reskinning.
- Chart colors live separately in `src/lib/vegaTheme.ts` and some are hardcoded in `src/lib/specs/highlights.ts` and `src/components/dashboard/CostSummaryPanel.tsx`.

### Feature flags

- `NEXT_PUBLIC_ENABLE_BUILDER` — Chart builder UI (default: off)
- `NEXT_PUBLIC_ENABLE_COMPARE` — Compare drawer + model comparison (default: off)

Defined in `src/lib/featureFlags.ts`.

## Tech stack

Next.js 16, React 19, Tailwind CSS 4 (PostCSS plugin, no tailwind.config), Vega-Lite 6, Zustand 5, SWR 2, Radix UI (popover), PostHog analytics, AWS S3 SDK.

## Environment

Copy `.env.example` to `.env` and fill in S3 credentials. `OPENROUTER_API_KEY` enables live pricing; omit it to use the bundled snapshot.
