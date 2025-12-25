# PostHog post-wizard report

The wizard has completed a deep integration of your DebateBench dashboard project. PostHog has been configured to track key user interactions across the application, including model comparison activities, filter usage, chart building, data downloads, and navigation patterns. The integration uses the modern `instrumentation-client.ts` approach for Next.js 15.3+, with automatic pageview capture, exception tracking, and custom event tracking throughout the application.

## Integration Summary

- **PostHog JS SDK**: Installed via pnpm (`posthog-js@1.310.1`)
- **Initialization**: Using `instrumentation-client.ts` (Next.js 15.3+ recommended approach)
- **Environment Variables**: Added `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST` to `.env`
- **Error Tracking**: Enabled via `capture_exceptions: true`
- **Automatic Pageviews**: Enabled via `defaults: '2025-11-30'`

## Events Instrumented

| Event Name | Description | File Path |
|------------|-------------|-----------|
| `model_added_to_compare` | User adds a model to the comparison selection for custom charts | `src/hooks/useCompareQuery.ts` |
| `model_removed_from_compare` | User removes a model from the comparison selection | `src/hooks/useCompareQuery.ts` |
| `category_filter_changed` | User changes the category filter selection on the dashboard | `src/components/dashboard/FilterBar.tsx` |
| `model_filter_changed` | User changes the model filter selection on the dashboard | `src/components/dashboard/FilterBar.tsx` |
| `filters_reset` | User clears all filters (categories and models) on the dashboard | `src/components/dashboard/FilterBar.tsx` |
| `run_changed` | User selects a different run/dataset to view | `src/components/dashboard/RunControls.tsx` |
| `data_downloaded` | User downloads the debates data as JSONL file | `src/components/dashboard/RunControls.tsx` |
| `data_refreshed` | User manually refreshes the dashboard data | `src/components/dashboard/RunControls.tsx` |
| `highlights_tab_changed` | User switches between performance, efficiency, and cost tabs in highlights | `src/components/dashboard/HighlightLists.tsx` |
| `chart_built` | User builds a custom chart with selected parameters in the builder | `src/app/builder/BuilderClient.tsx` |
| `chart_type_changed` | User changes the chart type (bar, scatter, heatmap) in the builder | `src/app/builder/BuilderClient.tsx` |
| `compare_drawer_opened` | User opens the compare drawer to view selected models for comparison | `src/components/dashboard/CompareDrawer.tsx` |
| `price_perf_metric_changed` | User switches between Elo and Win Rate in the price to performance chart | `src/app/page.tsx` |

## Files Modified

- `.env` - Added PostHog environment variables
- `instrumentation-client.ts` - Created for PostHog client-side initialization
- `src/hooks/useCompareQuery.ts` - Added model comparison tracking
- `src/components/dashboard/FilterBar.tsx` - Added filter interaction tracking
- `src/components/dashboard/RunControls.tsx` - Added run selection and data download tracking
- `src/components/dashboard/HighlightLists.tsx` - Added highlights tab tracking
- `src/app/builder/BuilderClient.tsx` - Added chart builder tracking with error capture
- `src/components/dashboard/CompareDrawer.tsx` - Added drawer interaction tracking
- `src/app/page.tsx` - Added price/performance metric toggle tracking

## Next steps

We've built some insights and a dashboard for you to keep an eye on user behavior, based on the events we just instrumented:

### Dashboard

- [Analytics basics](https://us.posthog.com/project/272448/dashboard/941874) - Core analytics dashboard with all key metrics

### Insights

- [Models Added to Compare - Daily Trend](https://us.posthog.com/project/272448/insights/Y7FVVXDL) - Tracks model comparison engagement
- [Chart Builder Usage](https://us.posthog.com/project/272448/insights/zWsr3g2e) - Tracks custom chart creation by chart type
- [Data Downloads](https://us.posthog.com/project/272448/insights/VBNRBJkP) - Key conversion metric for data exports
- [Filter Usage Breakdown](https://us.posthog.com/project/272448/insights/TI3Qh4rB) - Shows category and model filter interactions
- [Highlights Tab Engagement](https://us.posthog.com/project/272448/insights/dvRkdBTw) - Tracks which highlights tabs users prefer

## Getting Started

1. Run your development server: `pnpm dev`
2. Visit your application and interact with features
3. Check your PostHog dashboard to see events coming in
4. Explore the pre-built insights to understand user behavior
