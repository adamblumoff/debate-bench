# UI Overhaul Plan (Dark Mode, Inspired Layout)

## Objectives
- Deliver a dark, high-contrast experience that borrows the layout rhythm (hero + highlights + discovery + deep dives) without reusing any source content or chart data.
- Improve scannability and comparison flow for models/tasks; reduce nav clutter; keep performance smooth for data-heavy views.
- Preserve responsiveness for desktop, tablet, and mobile with minimal duplicate components.

## Guiding Principles
- Dark base: near-black `#0c0f12` background; warm-gray surfaces; off-white text; single electric-blue accent; amber for warnings/trends.
- Information hierarchy: Hero → Highlights (tabbed) → Filters/Compare → Charts/Tables → Insights/help.
- Content originality: all labels/metrics/titles are ours; no reuse of external chart copy or ordering.
- Low cognitive load: fewer simultaneous panels; progressive disclosure via tabs, drawers, and popovers.

## Information Architecture & Layout
- **Top nav:** 5–6 primary items + “More” overflow; right side: command palette trigger, theme toggle, account menu.
- **Hero band:** dark gradient; single CTA (“Explore evaluations”) + secondary text pill (e.g., “342 models • Q4 2025”).
- **Highlights block:** single card with tabs (Performance, Latency, Cost). Each tab shows 3–5 mini bar/stack charts with tooltips; optional toggle for linear/log scale and top-N chip.
- **Discovery tiles:** 2×2 card grid of entry points (e.g., “Fastest small models”, “Best price for chat”, “Multimodal leaders”, “Long-context champs”).
- **Filters strip (sticky):** Model family, Task type, Release window, Context length, Price band; compact chips; clear-all + save preset.
- **Compare drawer:** pin 2–4 models; shows side-by-side key metrics and sparkline history; slide-up on mobile.
- **Main analysis area:** split tabs (Charts | Table | Notes). Charts default to combined view; table offers column toggles and inline sparklines; notes host analyst annotations and data caveats.
- **Context rail:** collapsible right-side info (methodology, datasets, last updated) accessed via “?” chips.
- **Footer:** social links relocated here; include data refresh timestamp and feedback link.

## Visual System
- Typography: one display face for headings (e.g., “Sora Variable”), one humanist sans for body (e.g., “Source Sans 3”); 14–32px scale with consistent line heights.
- Color tokens: `bg_base`, `bg_surface`, `text_primary`, `text_muted`, `accent_primary`, `accent_warning`, `border_subtle`, `chart_palette` array tuned for dark.
- Components: glassy cards with subtle 1px borders + 6–8px radius; hover elevation via shadow + border glow in accent.
- Charts: muted palettes; highlight selected series; animate only on first render; small trend arrows showing delta since prior period.

## Interaction & UX Details
- Command palette (`⌘/Ctrl+K`) for navigation and quick compare add.
- Tooltips show metric, unit, source, and evaluation date; include “copy metric link.”
- Tabs and filters preserve state per session (local storage).
- Skeleton loaders for charts/tables; optimistic UI for pinning compares.
- Keyboard support: focus rings in accent; `Tab` order matches layout; `Esc` closes drawers/palettes.

## Data & Content Rules
- Invent our own metric names and values; avoid external ordering/labels.
- Provide unit labels on every chart axis; allow metric definitions via inline popover.
- Show “last updated” and data source badge on highlight cards.

## Responsiveness
- Desktop: three-column feel (main, filters bar, optional context rail).
- Tablet: context rail collapses; filters turn into horizontal scroll chips.
- Mobile: bottom nav with 4 icons; charts scroll horizontally; compare drawer becomes full-height modal.

## Performance & Tech Notes
- Lazy-load heavy chart modules; memoize filtered datasets.
- Prefer canvas/WebGL charts for large series; SVG for small multiples.
- Respect reduced-motion setting; cap animation to 150–200ms.

## Rollout Steps
- Build theme tokens + typography in a shared design system file.
- Implement layout skeleton (nav, hero, tabbed highlights, discovery grid, sticky filters, compare drawer).
- Wire sample data for charts/tables with placeholder metrics to validate flows.
- Add interactions (palette, tooltips, pin-to-compare, filter persistence).
- Accessibility pass (contrast, focus, aria-labels on charts, keyboard paths).
- Responsive QA across breakpoints; performance checks on chart load.

## Open Questions
- Which 3–5 metrics are core for the Highlights tabs?
- Do we need a “live pricing” badge sourced externally, or will we ingest snapshots?
- Should compare drawer sync with URL query params for shareable states?

