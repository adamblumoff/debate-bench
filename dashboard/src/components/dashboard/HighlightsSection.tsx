import { HighlightsTabs, MiniBarList, TokenBarList } from "@/components/dashboard/HighlightLists";
import { ChartCard } from "@/components/ChartCard";
import { LoadState } from "@/components/LoadState";
import { VegaLiteChart } from "@/components/VegaLiteChart";
import { HighlightLists, HighlightSpecs } from "@/lib/highlights";
import { PricingSnapshot } from "@/lib/pricing";
import { DerivedData } from "@/lib/types";
import { HighlightsTab } from "@/hooks/useHighlightsState";

type Props = {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  derived?: DerivedData;
  specs: HighlightSpecs;
  highlightData: HighlightLists;
  activeTab: HighlightsTab;
  onTab: (tab: HighlightsTab) => void;
  onAddModel: (id: string) => void;
  pricing: PricingSnapshot;
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
}: Props) {
  if (status !== "ready" || !derived) {
    return (
      <div className="card">
        <LoadState status={status} error={error} />
      </div>
    );
  }

  return (
    <section id="highlights" className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Highlights</p>
          <h2 className="text-2xl font-semibold text-white">Performance at a glance</h2>
        </div>
        <HighlightsTabs active={activeTab} onChange={onTab} />
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {activeTab === "performance" && (
          <>
            <MiniBarList title="Elo leaderboard" items={highlightData.elo} formatter={(v) => v.toFixed(0)} onAdd={onAddModel} />
            <MiniBarList title="Win rate" items={highlightData.win} formatter={(v) => `${(v * 100).toFixed(1)}%`} onAdd={onAddModel} />
            <ChartCard title="Elo vs win rate">{specs.ratingVsWin && <VegaLiteChart spec={specs.ratingVsWin} />}</ChartCard>
          </>
        )}
        {activeTab === "efficiency" && (
          <>
            <TokenBarList title="Mean tokens (prompt/output)" items={highlightData.tokens} onAdd={onAddModel} />
            <ChartCard title="Token stack (top N)">{specs.tokens && <VegaLiteChart spec={specs.tokens} />}</ChartCard>
            <MiniBarList title="Side bias spread" items={highlightData.sideBias} formatter={(v) => `${(v * 100).toFixed(1)}%`} onAdd={onAddModel} />
          </>
        )}
        {activeTab === "cost" && (
          <>
            <MiniBarList title="Cheapest blended cost" items={highlightData.cost} formatter={(v) => `$${v.toFixed(2)}`} onAdd={onAddModel} />
            <div className="card col-span-2 flex flex-col justify-between">
              <div>
                <p className="text-sm text-slate-300 mb-1">Pricing snapshot</p>
                <p className="text-xs text-slate-500">
                  Updated {pricing.updated} • {pricing.currency} per 1M tokens
                </p>
              </div>
              <div className="mt-3">
                <a href="#pricing" className="btn-ghost inline-block">
                  View pricing table
                </a>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
