"use client";

import { Suspense, useMemo, useCallback, useState } from "react";
import { ChartCard } from "@/components/ChartCard";
import { LoadState } from "@/components/LoadState";
import { VegaLiteChart } from "@/components/VegaLiteChart";
import { ChartBuilder } from "@/components/ChartBuilder";
import { useEnsureData } from "@/store/useDataStore";
import { useHighlightsState } from "@/hooks/useHighlightsState";
import { useCompareQuery } from "@/hooks/useCompareQuery";
import { usePricingData } from "@/hooks/usePricingData";
import { Hero } from "@/components/dashboard/Hero";
import { FilterBar } from "@/components/dashboard/FilterBar";
import { CompareDrawer } from "@/components/dashboard/CompareDrawer";
import { PricingTable } from "@/components/dashboard/PricingTable";
import { HighlightsTabs, MiniBarList, TokenBarList } from "@/components/dashboard/HighlightLists";
import { buildCategoryHeatSpec, buildH2HSpec, buildJudgeHeatSpec, buildSideBiasSpec } from "@/lib/specs/core";
import { buildLeaderboardSpec, buildRatingVsWinSpec, buildTokenStackSpec, buildWinrateSpec } from "@/lib/specs/highlights";
import { toPercent } from "@/lib/format";
import { buildDerived } from "@/lib/metrics";

function DashboardContent() {
  const { status, error, derived, debates } = useEnsureData();
  const { activeTab, setActiveTab, topN, setTopN, category, setCategory } = useHighlightsState();
  const { selected: compareModels, addModel: addCompareModel, removeModel } = useCompareQuery();
  const filteredDebates = useMemo(
    () => (category === "all" ? debates : debates.filter((d) => (d.transcript.topic.category || "") === category)),
    [debates, category]
  );
  const filteredDerived = useMemo(() => {
    if (!derived) return undefined;
    if (category === "all") return derived;
    return buildDerived(filteredDebates);
  }, [derived, category, filteredDebates]);
  const modelIds = filteredDerived?.modelStats.map((m) => m.model_id) || [];
  const pricing = usePricingData(modelIds);
  const [compareOpen, setCompareOpen] = useState(false);
  const [lastAdded, setLastAdded] = useState<number>();

  const addModel = useCallback(
    (id: string) => {
      addCompareModel(id);
      setCompareOpen(true);
      setLastAdded(Date.now());
    },
    [addCompareModel]
  );

  const categories = useMemo(() => {
    if (!filteredDerived) return [];
    const seen = new Set<string>();
    const list: string[] = [];
    for (const t of filteredDerived.topicWinrates) {
      if (!t.category) continue;
      if (seen.has(t.category)) continue;
      seen.add(t.category);
      list.push(t.category);
    }
    return list;
  }, [filteredDerived]);

  const specs = useMemo(() => {
    if (!filteredDerived) return {};
    return {
      leaderboard: buildLeaderboardSpec(filteredDerived, topN),
      winrate: buildWinrateSpec(filteredDerived, topN),
      sideBias: buildSideBiasSpec(filteredDerived, topN),
      h2h: buildH2HSpec(filteredDerived),
      judgeHeat: buildJudgeHeatSpec(filteredDerived),
      categoryHeat: buildCategoryHeatSpec(filteredDerived, category),
      tokens: buildTokenStackSpec(filteredDerived, topN),
      ratingVsWin: buildRatingVsWinSpec(filteredDerived),
    };
  }, [filteredDerived, topN, category]);

  const highlightData = useMemo(() => {
    if (!filteredDerived) return { elo: [], win: [], tokens: [], cost: [], sideBias: [] };
    const elo = filteredDerived.modelStats.slice(0, topN).map((m) => ({ label: m.model_id, value: m.rating, hint: toPercent(m.win_rate) }));
    const win = [...filteredDerived.modelStats].sort((a, b) => b.win_rate - a.win_rate).slice(0, topN).map((m) => ({ label: m.model_id, value: m.win_rate, hint: `Games ${m.games}` }));
    const tokens = filteredDerived.modelStats
      .slice(0, topN)
      .map((m) => ({ label: m.model_id, prompt: m.mean_prompt_tokens, output: m.mean_completion_tokens }));
    const cost = [...pricing.rows]
      .sort((a, b) => a.input_per_million + a.output_per_million - (b.input_per_million + b.output_per_million))
      .slice(0, 6)
      .map((r) => ({ label: r.model_id, value: r.input_per_million + r.output_per_million, hint: `${pricing.currency} in/out` }));
    const sideBias = [...filteredDerived.modelStats]
      .map((m) => {
        const gap = (m.pro_win_rate || 0) - (m.con_win_rate || 0);
        return {
          label: m.model_id,
          value: Math.abs(gap),
          hint: `${gap >= 0 ? "+" : ""}${toPercent(gap)} • Pro ${toPercent(m.pro_win_rate)} / Con ${toPercent(m.con_win_rate)}`,
        };
      })
      .sort((a, b) => b.value - a.value)
      .slice(0, topN);
    return { elo, win, tokens, cost, sideBias };
  }, [filteredDerived, topN, pricing]);

  const kpi = useMemo(() => {
    if (!filteredDerived || !filteredDerived.modelStats.length) return null;
    const top = filteredDerived.modelStats[0];
    const widestGap = [...filteredDerived.modelStats].sort((a, b) => Math.abs(b.pro_win_rate - b.con_win_rate) - Math.abs(a.pro_win_rate - a.con_win_rate))[0];
    const judgeRange = filteredDerived.judgeAgreement.reduce(
      (acc, j) => {
        acc.min = Math.min(acc.min, j.agreement_rate);
        acc.max = Math.max(acc.max, j.agreement_rate);
        return acc;
      },
      { min: filteredDerived.judgeAgreement.length ? 1 : 0, max: filteredDerived.judgeAgreement.length ? 0 : 0 }
    );
    return {
      topModel: `${top.model_id} (${toPercent(top.win_rate)})`,
      sideGap: `${widestGap.model_id}: ${toPercent(widestGap.pro_win_rate - widestGap.con_win_rate)}`,
      judgeSpan: `${toPercent(judgeRange.min)} – ${toPercent(judgeRange.max)}`,
    };
  }, [filteredDerived]);

  return (
    <main className="min-h-screen text-slate-50 bg-[var(--bg-base)]">
      <div className="container-page space-y-8 pb-28">
        <Hero debateCount={filteredDebates.length} modelCount={filteredDerived?.models.length || 0} />

        <FilterBar categories={categories} category={category} onCategory={setCategory} topN={topN} onTopN={setTopN} />

        <section id="highlights" className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Highlights</p>
              <h2 className="text-2xl font-semibold text-white">Performance at a glance</h2>
            </div>
            <HighlightsTabs active={activeTab} onChange={setActiveTab} />
          </div>
          {status === "ready" && derived ? (
            <div className="grid gap-3 md:grid-cols-3">
              {activeTab === "performance" && (
                <>
                  <MiniBarList title="Elo leaderboard" items={highlightData.elo} formatter={(v) => v.toFixed(0)} onAdd={addModel} />
                  <MiniBarList title="Win rate" items={highlightData.win} formatter={(v) => toPercent(v)} onAdd={addModel} />
                  <ChartCard title="Elo vs win rate">{specs.ratingVsWin && <VegaLiteChart spec={specs.ratingVsWin} />}</ChartCard>
                </>
              )}
              {activeTab === "efficiency" && (
                <>
                  <TokenBarList title="Mean tokens (prompt/output)" items={highlightData.tokens} onAdd={addModel} />
                  <ChartCard title="Token stack (top N)">{specs.tokens && <VegaLiteChart spec={specs.tokens} />}</ChartCard>
                  <MiniBarList title="Side bias spread" items={highlightData.sideBias} formatter={(v) => toPercent(v)} onAdd={addModel} />
                </>
              )}
              {activeTab === "cost" && (
                <>
                  <MiniBarList title="Cheapest blended cost" items={highlightData.cost} formatter={(v) => `$${v.toFixed(2)}`} onAdd={addModel} />
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
          ) : (
            <div className="card">
              <LoadState status={status} error={error} />
            </div>
          )}
        </section>

        {status === "ready" && derived ? (
          <div className="space-y-6">
            <section id="overview" className="space-y-4">
              {kpi && (
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="kpi-tile">
                    <p className="text-xs uppercase tracking-wide text-slate-400">Top model</p>
                    <p className="text-lg font-semibold text-white">{kpi.topModel}</p>
                  </div>
                  <div className="kpi-tile">
                    <p className="text-xs uppercase tracking-wide text-slate-400">Widest side gap</p>
                    <p className="text-lg font-semibold text-white">{kpi.sideGap}</p>
                  </div>
                  <div className="kpi-tile">
                    <p className="text-xs uppercase tracking-wide text-slate-400">Judge agreement span</p>
                    <p className="text-lg font-semibold text-white">{kpi.judgeSpan}</p>
                  </div>
                </div>
              )}
            </section>

            <section id="models" className="grid gap-4 md:grid-cols-2">
              <ChartCard title="Elo leaderboard">{specs.leaderboard && <VegaLiteChart spec={specs.leaderboard} />}</ChartCard>
              <ChartCard title="Win rate (top N)">{specs.winrate && <VegaLiteChart spec={specs.winrate} />}</ChartCard>
            </section>

            <section id="topics" className="grid gap-4 md:grid-cols-2">
              <ChartCard title="Head-to-head win rate" subtitle="Row model vs column model">
                {specs.h2h && <VegaLiteChart spec={specs.h2h} />}
              </ChartCard>
              <ChartCard title="Topic/category win rates" subtitle="Per model × category heatmap">
                {specs.categoryHeat && <VegaLiteChart spec={specs.categoryHeat} />}
              </ChartCard>
            </section>

            <section id="judges" className="grid gap-4 md:grid-cols-2">
              <ChartCard title="Judge agreement">{specs.judgeHeat && <VegaLiteChart spec={specs.judgeHeat} />}</ChartCard>
              <ChartCard title="Side bias (pro minus con win rate)">{specs.sideBias && <VegaLiteChart spec={specs.sideBias} />}</ChartCard>
            </section>

            <section id="pricing" className="space-y-3">
              <PricingTable pricing={pricing} onAdd={addModel} />
            </section>

            <section id="builder" className="grid gap-4 md:grid-cols-2">
              <div className="card">
                <h3 className="text-lg font-semibold text-white mb-2">Notes</h3>
                <ul className="text-sm text-slate-300 list-disc pl-4 space-y-1">
                  <li>Highlights respect Top N and category filters for topic heatmaps.</li>
                  <li>Compare drawer is shareable (see URL query).</li>
                  <li>Token metrics use mean per-turn prompt and completion tokens.</li>
                </ul>
              </div>
              <ChartCard title="Custom chart builder" subtitle="Pick fields and chart type">
                <ChartBuilder data={derived} />
              </ChartCard>
            </section>
          </div>
        ) : (
          <div className="card text-slate-200">
            <LoadState status={status} error={error} />
            {status === "idle" && <p className="text-sm text-slate-400">Initializing data loader…</p>}
            {status === "loading" && <div className="mt-3 h-32 skeleton" />}
          </div>
        )}
      </div>

      <CompareDrawer models={compareModels} onRemove={removeModel} derived={derived} open={compareOpen} setOpen={setCompareOpen} lastAdded={lastAdded} />
    </main>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="container-page text-slate-400">Loading dashboard…</div>}>
      <DashboardContent />
    </Suspense>
  );
}
