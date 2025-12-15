import {
  HighlightsTabs,
  MiniBarList,
  TokenBarList,
} from "@/components/dashboard/HighlightLists";
import { ChartCard } from "@/components/ChartCard";
import { LoadState } from "@/components/LoadState";
import { VegaLiteChart } from "@/components/VegaLiteChart";
import { HighlightLists, HighlightSpecs } from "@/lib/highlights";
import { PricingSnapshot } from "@/lib/pricing";
import { DerivedData, RecentCostSummary } from "@/lib/types";
import { HighlightsTab } from "@/hooks/useHighlightsState";
import { RecentCostPanel } from "@/components/dashboard/RecentCostPanel";

type Props = {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  derived?: DerivedData;
  specs: HighlightSpecs;
  highlightData: HighlightLists;
  activeTab: HighlightsTab;
  onTab: (tab: HighlightsTab) => void;
  onAddModel?: (id: string) => void;
  pricing: PricingSnapshot;
  recentCost?: RecentCostSummary;
  topN: number;
  modelCount?: number;
  onResetFilters?: () => void;
};

export function HighlightsSection({
  status,
  error,
  derived,
  specs,
  highlightData,
  activeTab,
  onTab,
  onAddModel,
  pricing,
  recentCost,
  topN,
  modelCount,
  onResetFilters,
}: Props) {
  if (status !== "ready" || !derived) {
    return (
      <section id="highlights" className="space-y-3">
        <div className="card">
          <LoadState status={status} error={error} />
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton-block" />
            ))}
          </div>
        </div>
      </section>
    );
  }

  const noResults =
    highlightData.elo.length === 0 ||
    highlightData.win.length === 0 ||
    derived.modelStats.length === 0;

  if (noResults) {
    return (
      <section id="highlights" className="space-y-3">
        <div className="card empty-card flex flex-col gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
              Highlights
            </p>
            <h2 className="text-xl font-semibold text-white">
              No debates match these filters
            </h2>
            <p className="text-sm text-slate-400">
              Try clearing filters or selecting a different run to see results.
            </p>
          </div>
          {onResetFilters && (
            <div>
              <button className="btn-primary" onClick={onResetFilters}>
                Reset filters
              </button>
            </div>
          )}
        </div>
      </section>
    );
  }

  return (
    <section id="highlights" className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
            Highlights
          </p>
          <h2 className="text-2xl font-semibold text-white">
            {activeTab === "performance"
              ? "Performance at a glance"
              : activeTab === "efficiency"
                ? "Efficiency at a glance"
                : "Cost at a glance"}
          </h2>
        </div>
        <HighlightsTabs active={activeTab} onChange={onTab} />
      </div>

      {activeTab === "performance" && (
        <div className="grid gap-3 md:grid-cols-3">
          <div className="flex min-w-0">
            <MiniBarList
              title="Elo leaderboard"
              items={highlightData.elo}
              formatter={(v) => v.toFixed(0)}
              onAdd={onAddModel}
              expected={modelCount ?? topN}
              className="h-full w-full"
            />
          </div>
          <div className="flex min-w-0">
            <MiniBarList
              title="Win rate"
              items={highlightData.win}
              formatter={(v) => `${(v * 100).toFixed(1)}%`}
              onAdd={onAddModel}
              expected={modelCount ?? topN}
              className="h-full w-full"
            />
          </div>
          <div className="flex min-w-0">
            <ChartCard
              title="Elo vs win rate"
              className="chart-card highlight-card h-full w-full"
            >
              {specs.ratingVsWin && <VegaLiteChart spec={specs.ratingVsWin} />}
            </ChartCard>
          </div>
        </div>
      )}

      {activeTab === "efficiency" && (
        <div className="grid gap-3 md:grid-cols-3">
          <div className="flex min-w-0">
            <TokenBarList
              title="Mean tokens (prompt/output)"
              items={highlightData.tokens}
              onAdd={onAddModel}
              className="h-full w-full"
            />
          </div>
          <div className="flex min-w-0">
            <ChartCard
              title="Token stack (per run)"
              className="chart-card highlight-card h-full w-full"
            >
              {specs.tokens && <VegaLiteChart spec={specs.tokens} />}
            </ChartCard>
          </div>
          <div className="flex min-w-0">
            <MiniBarList
              title="Side bias spread"
              items={highlightData.sideBias}
              formatter={(v) => `${(v * 100).toFixed(1)}%`}
              onAdd={onAddModel}
              className="h-full w-full"
            />
          </div>
        </div>
      )}

      {activeTab === "cost" && (
        <div className="grid gap-3 md:grid-cols-12">
          <div className="md:col-span-4 flex min-w-0">
            <MiniBarList
              title="Lowest observed $/1M tokens"
              items={highlightData.cost}
              formatter={(v) => `$${v.toFixed(2)}`}
              onAdd={onAddModel}
              expected={modelCount ?? topN}
              className="h-full w-full"
            />
          </div>
          <div className="col-span-12 md:col-span-8 min-w-0">
            <RecentCostPanel recentCost={recentCost} pricing={pricing} />
          </div>
        </div>
      )}
    </section>
  );
}
