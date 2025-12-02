"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChartCard } from "@/components/ChartCard";
import { LoadState } from "@/components/LoadState";
import { VegaLiteChart } from "@/components/VegaLiteChart";
import { ChartBuilder } from "@/components/ChartBuilder";
import { useEnsureData } from "@/store/useDataStore";
import { DerivedData } from "@/lib/types";
import { VisualizationSpec } from "vega-embed";

const toPercent = (v: number) => `${(v * 100).toFixed(1)}%`;
const toTokens = (v: number) => `${Math.round(v).toLocaleString()} tok`;

type Specs = {
  leaderboard?: VisualizationSpec;
  sideBias?: VisualizationSpec;
  h2h?: VisualizationSpec;
  judgeHeat?: VisualizationSpec;
  categoryHeat?: VisualizationSpec;
  tokens?: VisualizationSpec;
  ratingVsWin?: VisualizationSpec;
  winrate?: VisualizationSpec;
};

function useSpecs(derived?: DerivedData, options: { limit?: number; category?: string } = {}): Specs {
  const { limit = 6, category = "all" } = options;
  return useMemo<Specs>(() => {
    if (!derived) return {};
    const topStats = derived.modelStats.slice(0, limit);
    const topWin = [...derived.modelStats].sort((a, b) => b.win_rate - a.win_rate).slice(0, limit);

    const leaderboard = {
      width: "container",
      height: 260,
      data: { values: topStats },
      mark: { type: "bar" },
      encoding: {
        y: { field: "model_id", type: "nominal", sort: "-x" },
        x: { field: "rating", type: "quantitative", axis: { title: "Elo" } },
        color: { field: "rating", type: "quantitative", scale: { scheme: "blues" } },
        tooltip: [
          { field: "model_id", title: "Model" },
          { field: "rating", title: "Elo", format: ".0f" },
          { field: "win_rate", title: "Win rate", format: ".1%" },
        ],
      },
    } satisfies VisualizationSpec;

    const winrate = {
      width: "container",
      height: 260,
      data: { values: topWin },
      mark: { type: "bar" },
      encoding: {
        y: { field: "model_id", type: "nominal", sort: "-x" },
        x: { field: "win_rate", type: "quantitative", axis: { format: ".0%", title: "Win rate" } },
        color: { field: "win_rate", type: "quantitative", scale: { scheme: "purples" } },
      },
    } satisfies VisualizationSpec;

    const side = derived.modelStats.map((m) => ({
      model: m.model_id,
      gap: m.pro_win_rate - m.con_win_rate,
      pro: m.pro_win_rate,
      con: m.con_win_rate,
    }));
    side.sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap));
    const sideBias = {
      width: "container",
      height: 260,
      data: { values: side.slice(0, limit + 2) },
      mark: { type: "bar" },
      encoding: {
        x: { field: "gap", type: "quantitative", axis: { format: ".0%" } },
        y: { field: "model", type: "nominal", sort: "-x" },
        color: { field: "gap", type: "quantitative", scale: { scheme: "purpleorange" } },
      },
    } satisfies VisualizationSpec;

    const h2h = {
      width: "container",
      height: 320,
      data: { values: derived.headToHead },
      mark: { type: "rect" },
      encoding: {
        x: { field: "col", type: "nominal" },
        y: { field: "row", type: "nominal" },
        color: { field: "win_rate", type: "quantitative", scale: { scheme: "blues" }, legend: { format: ".0%" } },
        tooltip: [
          { field: "row", type: "nominal", title: "row" },
          { field: "col", type: "nominal", title: "col" },
          { field: "win_rate", type: "quantitative", title: "win %", format: ".1%" },
          { field: "samples", type: "quantitative", title: "n" },
        ],
      },
      config: { axis: { labelAngle: -45 } },
    } satisfies VisualizationSpec;

    const judgeHeat = {
      width: "container",
      height: 260,
      data: { values: derived.judgeAgreement },
      mark: { type: "rect" },
      encoding: {
        x: { field: "judge_a", type: "nominal" },
        y: { field: "judge_b", type: "nominal" },
        color: { field: "agreement_rate", type: "quantitative", scale: { scheme: "tealblues" }, legend: { format: ".0%" } },
        tooltip: [
          { field: "judge_a", type: "nominal" },
          { field: "judge_b", type: "nominal" },
          { field: "agreement_rate", type: "quantitative", format: ".1%" },
          { field: "samples", type: "quantitative" },
        ],
      },
      config: { axis: { labelAngle: -30 } },
    } satisfies VisualizationSpec;

    const categoryHeat = (() => {
      const rows = derived.topicWinrates
        .filter((t) => category === "all" || t.category === category)
        .map((t) => ({
          category: t.category || t.topic_id,
          model: t.model_id,
          win_rate: t.win_rate,
          wins: t.wins,
          samples: t.samples,
        }));
      return {
        width: "container",
        height: 320,
        data: { values: rows },
        mark: { type: "rect" },
        encoding: {
          x: { field: "category", type: "nominal", sort: "-y" },
          y: { field: "model", type: "nominal" },
          color: { field: "win_rate", type: "quantitative", scale: { scheme: "greens" }, legend: { format: ".0%" } },
          tooltip: [
            { field: "model", type: "nominal" },
            { field: "category", type: "nominal" },
            { field: "win_rate", type: "quantitative", format: ".1%" },
            { field: "wins", type: "quantitative" },
            { field: "samples", type: "quantitative" },
          ],
        },
        config: { axis: { labelAngle: -40 } },
      } satisfies VisualizationSpec;
    })();

    const tokenRows = topStats.flatMap((m) => [
      { model: m.model_id, kind: "prompt", tokens: m.mean_prompt_tokens },
      { model: m.model_id, kind: "output", tokens: m.mean_completion_tokens },
    ]);
    const tokens = {
      width: "container",
      height: 260,
      data: { values: tokenRows },
      mark: { type: "bar" },
      encoding: {
        y: { field: "model", type: "nominal", sort: "-x" },
        x: { field: "tokens", type: "quantitative", axis: { title: "Mean tokens" } },
        color: { field: "kind", type: "nominal", scale: { scheme: "teals" } },
      },
    } satisfies VisualizationSpec;

    const ratingVsWin = {
      width: "container",
      height: 260,
      data: { values: derived.modelStats },
      mark: { type: "point" },
      encoding: {
        x: { field: "rating", type: "quantitative", axis: { title: "Elo" } },
        y: { field: "win_rate", type: "quantitative", axis: { title: "Win rate", format: ".0%" } },
        color: { field: "mean_total_tokens", type: "quantitative", scale: { scheme: "oranges" }, legend: { title: "Mean tokens" } },
        tooltip: [
          { field: "model_id", title: "Model" },
          { field: "rating", title: "Elo", format: ".0f" },
          { field: "win_rate", title: "Win rate", format: ".1%" },
          { field: "mean_total_tokens", title: "Mean tokens", format: ".0f" },
        ],
      },
    } satisfies VisualizationSpec;

    return { leaderboard, sideBias, h2h, judgeHeat, categoryHeat, tokens, ratingVsWin, winrate };
  }, [derived, limit, category]);
}

function MiniBarList({
  title,
  items,
  formatter,
  onAdd,
}: {
  title: string;
  items: { label: string; value: number; hint?: string }[];
  formatter: (n: number) => string;
  onAdd?: (id: string) => void;
}) {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="card flex-1">
      <header className="flex items-center justify-between mb-2">
        <p className="text-sm text-slate-300">{title}</p>
        <div className="h-1 w-10 rounded-full bg-[var(--accent)]" />
      </header>
      <div className="space-y-2">
        {items.map((i) => (
          <div key={i.label} className="flex items-center gap-3">
            <div className="w-full">
              <div className="flex justify-between text-xs text-slate-400">
                <span>{i.label}</span>
                <span className="text-slate-200">{formatter(i.value)}</span>
              </div>
              <div className="h-2.5 rounded-full bg-slate-800/70 overflow-hidden">
                <div
                  className="h-full rounded-full bg-[var(--accent)]"
                  style={{ width: `${Math.max((i.value / max) * 100, 4)}%` }}
                />
              </div>
              {i.hint && <p className="text-[11px] text-slate-500 mt-0.5">{i.hint}</p>}
            </div>
            {onAdd && (
              <button
                className="text-xs px-2 py-1 rounded-md border border-[var(--border)] hover:border-[var(--accent)] text-slate-200"
                onClick={() => onAdd(i.label)}
              >
                + Compare
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function TokenBarList({
  title,
  items,
  onAdd,
}: {
  title: string;
  items: { label: string; prompt: number; output: number }[];
  onAdd?: (id: string) => void;
}) {
  const max = Math.max(...items.map((i) => i.prompt + i.output), 1);
  return (
    <div className="card flex-1">
      <header className="flex items-center justify-between mb-2">
        <p className="text-sm text-slate-300">{title}</p>
        <div className="h-1 w-10 rounded-full bg-[var(--accent)]" />
      </header>
      <div className="space-y-2">
        {items.map((i) => {
          const total = i.prompt + i.output;
          const promptPct = total ? (i.prompt / total) * 100 : 50;
          return (
            <div key={i.label} className="flex items-center gap-3">
              <div className="w-full">
                <div className="flex justify-between text-xs text-slate-400">
                  <span>{i.label}</span>
                  <span className="text-slate-200">{toTokens(total)}</span>
                </div>
                <div className="h-2.5 rounded-full bg-slate-800/70 overflow-hidden flex">
                  <div className="h-full bg-[var(--accent)]" style={{ width: `${(total / max) * 100}%` }}>
                    <div className="h-full bg-[var(--accent)]" style={{ width: `${promptPct}%`, opacity: 0.65 }} />
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {toTokens(i.prompt)} prompt • {toTokens(i.output)} output
                </p>
              </div>
              {onAdd && (
                <button
                  className="text-xs px-2 py-1 rounded-md border border-[var(--border)] hover:border-[var(--accent)] text-slate-200"
                  onClick={() => onAdd(i.label)}
                >
                  + Compare
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FilterBar({
  categories,
  category,
  onCategory,
  topN,
  onTopN,
}: {
  categories: string[];
  category: string;
  onCategory: (v: string) => void;
  topN: number;
  onTopN: (v: number) => void;
}) {
  return (
    <div className="filter-bar sticky top-0 z-20 backdrop-blur">
      <div className="filter-row">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Category</p>
            <div className="flex gap-2 flex-wrap">
              <button
                className={`chip ${category === "all" ? "active" : ""}`}
                onClick={() => onCategory("all")}
              >
                All
              </button>
              {categories.map((c) => (
                <button key={c} className={`chip ${category === c ? "active" : ""}`} onClick={() => onCategory(c)}>
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Top N</p>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={4}
                max={12}
                value={topN}
                onChange={(e) => onTopN(Number(e.target.value))}
              />
              <span className="text-sm text-slate-200">{topN}</span>
            </div>
          </div>
        </div>
        <div className="text-xs text-slate-400">
          Filters apply to highlights and category heatmaps; compare state is shareable via URL.
        </div>
      </div>
    </div>
  );
}

function DiscoveryTiles() {
  const tiles = [
    { title: "Fastest small models", desc: "Low-token, high win-rate picks", href: "#highlights" },
    { title: "Best price for chat", desc: "Price-per-million vs quality", href: "#pricing" },
    { title: "Multimodal leaders", desc: "By category performance", href: "#topics" },
    { title: "Long-context champs", desc: "Side bias & stability", href: "#judges" },
  ];
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {tiles.map((t) => (
        <a key={t.title} href={t.href} className="tile">
          <p className="text-sm font-semibold text-white">{t.title}</p>
          <p className="text-xs text-slate-400">{t.desc}</p>
        </a>
      ))}
    </div>
  );
}

function CompareDrawer({
  models,
  onRemove,
  derived,
}: {
  models: string[];
  onRemove: (id: string) => void;
  derived?: DerivedData;
}) {
  if (!models.length || !derived) return null;
  const rows = models
    .map((m) => derived.modelStats.find((s) => s.model_id === m))
    .filter(Boolean)
    .slice(0, 4);
  return (
    <div className="compare-drawer">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Compare</p>
          <h3 className="text-lg font-semibold text-white">Pinned models ({rows.length})</h3>
        </div>
        <div className="text-xs text-slate-400">Shareable via URL params</div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
        {rows.map((r) => (
          <div key={r!.model_id} className="compare-card">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-white">{r!.model_id}</p>
              <button className="text-xs text-slate-400 hover:text-red-300" onClick={() => onRemove(r!.model_id)}>
                remove
              </button>
            </div>
            <p className="text-sm text-slate-300">Elo {r!.rating.toFixed(0)} • Win {toPercent(r!.win_rate)}</p>
            <p className="text-xs text-slate-500">
              Tokens {toTokens(r!.mean_prompt_tokens)} / {toTokens(r!.mean_completion_tokens)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function useCompareQuery() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const parseParams = useCallback(() => {
    const params = searchParams;
    const values = params.getAll("compare");
    if (values.length === 1 && values[0].includes(",")) {
      return values[0].split(",").filter(Boolean);
    }
    return values;
  }, [searchParams]);

  const [selected, setSelected] = useState<string[]>(parseParams);

  useEffect(() => {
    setSelected(parseParams());
  }, [parseParams]);

  const updateQuery = useCallback(
    (next: string[]) => {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("compare");
      next.forEach((c) => params.append("compare", c));
      router.replace(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const addModel = useCallback(
    (id: string) => {
      setSelected((prev) => {
        if (prev.includes(id)) return prev;
        const next = [...prev, id].slice(-4);
        updateQuery(next);
        return next;
      });
    },
    [updateQuery]
  );

  const removeModel = useCallback(
    (id: string) => {
      setSelected((prev) => {
        const next = prev.filter((m) => m !== id);
        updateQuery(next);
        return next;
      });
    },
    [updateQuery]
  );

  return { selected, addModel, removeModel };
}

function Hero({ debateCount, modelCount }: { debateCount: number; modelCount: number }) {
  return (
    <header className="hero">
      <div className="flex items-center gap-4">
        <div className="logo-pill">DB</div>
        <div>
          <p className="text-xs tracking-[0.28em] text-slate-400">DEBATEBENCH</p>
          <h1 className="text-4xl font-semibold text-white">Interactive Results Dashboard</h1>
          <p className="text-slate-400 text-sm">Live benchmarks • {modelCount} models • {debateCount} debates</p>
        </div>
      </div>
      <div className="hero-cta">
        <a href="#highlights" className="btn-primary">Explore evaluations</a>
        <a href="#builder" className="btn-ghost">Open builder</a>
      </div>
    </header>
  );
}

function DashboardPage() {
  const { status, error, derived, debates } = useEnsureData();
  const [activeTab, setActiveTab] = useState<"performance" | "efficiency" | "cost">("performance");
  const [topN, setTopN] = useState(6);
  const [category, setCategory] = useState<string>("all");
  const { selected: compareModels, addModel, removeModel } = useCompareQuery();

  const categories = useMemo(
    () => (derived ? Array.from(new Set(derived.topicWinrates.map((t) => t.category).filter(Boolean) as string[])) : []),
    [derived]
  );

  const specs = useSpecs(derived, { limit: topN, category });

  const highlightData = useMemo(() => {
    if (!derived) return { elo: [], win: [], tokens: [] };
    const elo = derived.modelStats.slice(0, topN).map((m) => ({ label: m.model_id, value: m.rating, hint: toPercent(m.win_rate) }));
    const win = [...derived.modelStats].sort((a, b) => b.win_rate - a.win_rate).slice(0, topN).map((m) => ({ label: m.model_id, value: m.win_rate, hint: `Games ${m.games}` }));
    const tokens = derived.modelStats
      .slice(0, topN)
      .map((m) => ({ label: m.model_id, prompt: m.mean_prompt_tokens, output: m.mean_completion_tokens }));
    return { elo, win, tokens };
  }, [derived, topN]);

  const kpi = useMemo(() => {
    if (!derived || !derived.modelStats.length) return null;
    const top = derived.modelStats[0];
    const widestGap = [...derived.modelStats].sort((a, b) => Math.abs(b.pro_win_rate - b.con_win_rate) - Math.abs(a.pro_win_rate - a.con_win_rate))[0];
    const judgeRange = derived.judgeAgreement.reduce(
      (acc, j) => {
        acc.min = Math.min(acc.min, j.agreement_rate);
        acc.max = Math.max(acc.max, j.agreement_rate);
        return acc;
      },
      { min: derived.judgeAgreement.length ? 1 : 0, max: derived.judgeAgreement.length ? 0 : 0 }
    );
    return {
      topModel: `${top.model_id} (${toPercent(top.win_rate)})`,
      sideGap: `${widestGap.model_id}: ${toPercent(widestGap.pro_win_rate - widestGap.con_win_rate)}`,
      judgeSpan: `${toPercent(judgeRange.min)} – ${toPercent(judgeRange.max)}`,
    };
  }, [derived]);

  return (
    <main className="min-h-screen text-slate-50 bg-[var(--bg-base)]">
      <div className="container-page space-y-8 pb-28">
        <Hero debateCount={debates.length} modelCount={derived?.models.length || 0} />

        <FilterBar categories={categories} category={category} onCategory={setCategory} topN={topN} onTopN={setTopN} />

        <section id="highlights" className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Highlights</p>
              <h2 className="text-2xl font-semibold text-white">Performance at a glance</h2>
            </div>
            <div className="tab-switch">
              {(["performance", "efficiency", "cost"] as const).map((t) => (
                <button key={t} className={activeTab === t ? "active" : ""} onClick={() => setActiveTab(t)}>
                  {t === "performance" ? "Performance" : t === "efficiency" ? "Efficiency" : "Cost"}
                </button>
              ))}
            </div>
          </div>
          {status === "ready" && derived ? (
            <div className="grid gap-3 md:grid-cols-3">
              {activeTab === "performance" && (
                <>
                  <MiniBarList title="Elo leaderboard" items={highlightData.elo} formatter={(v) => v.toFixed(0)} onAdd={addModel} />
                  <MiniBarList title="Win rate" items={highlightData.win} formatter={(v) => toPercent(v)} onAdd={addModel} />
                  <ChartCard title="Elo vs win rate">
                    {specs.ratingVsWin && <VegaLiteChart spec={specs.ratingVsWin} />}
                  </ChartCard>
                </>
              )}
              {activeTab === "efficiency" && (
                <>
                  <TokenBarList title="Mean tokens (prompt/output)" items={highlightData.tokens} onAdd={addModel} />
                  <ChartCard title="Token stack (top N)">
                    {specs.tokens && <VegaLiteChart spec={specs.tokens} />}
                  </ChartCard>
                  <MiniBarList title="Side bias spread" items={highlightData.elo.slice(0, 4)} formatter={(v) => v.toFixed(0)} onAdd={addModel} />
                </>
              )}
              {activeTab === "cost" && (
                <>
                  <div className="card col-span-2">
                    <p className="text-sm text-slate-300 mb-2">Cost snapshot</p>
                    <p className="text-xs text-slate-500">Live pricing TBD — showing placeholder snapshot with last-updated badge.</p>
                  </div>
                  <MiniBarList title="Win rate" items={highlightData.win.slice(0, 3)} formatter={(v) => toPercent(v)} onAdd={addModel} />
                </>
              )}
            </div>
          ) : (
            <div className="card">
              <LoadState status={status} error={error} />
            </div>
          )}
        </section>

        <DiscoveryTiles />

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
              <ChartCard title="Elo leaderboard">
                {specs.leaderboard && <VegaLiteChart spec={specs.leaderboard} />}
              </ChartCard>
              <ChartCard title="Win rate (top N)">
                {specs.winrate && <VegaLiteChart spec={specs.winrate} />}
              </ChartCard>
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
              <ChartCard title="Judge agreement">
                {specs.judgeHeat && <VegaLiteChart spec={specs.judgeHeat} />}
              </ChartCard>
              <ChartCard title="Side bias (pro minus con win rate)">
                {specs.sideBias && <VegaLiteChart spec={specs.sideBias} />}
              </ChartCard>
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

      <CompareDrawer models={compareModels} onRemove={removeModel} derived={derived} />
    </main>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="container-page text-slate-400">Loading dashboard…</div>}>
      <DashboardPage />
    </Suspense>
  );
}
