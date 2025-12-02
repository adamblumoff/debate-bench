"use client";

import { useMemo } from "react";
import { ChartCard } from "@/components/ChartCard";
import { LoadState } from "@/components/LoadState";
import { VegaLiteChart } from "@/components/VegaLiteChart";
import { ChartBuilder } from "@/components/ChartBuilder";
import { useEnsureData } from "@/store/useDataStore";
import { DerivedData } from "@/lib/types";
// no-op imports removed
import { VisualizationSpec } from "vega-embed";

const toPercent = (v: number) => `${(v * 100).toFixed(1)}%`;


type Specs = {
  leaderboard?: VisualizationSpec;
  sideBias?: VisualizationSpec;
  h2h?: VisualizationSpec;
  judgeHeat?: VisualizationSpec;
  categoryHeat?: VisualizationSpec;
};

function useSpecs(derived?: DerivedData): Specs {
  return useMemo<Specs>(() => {
    if (!derived) return {};
    const top = derived.modelStats.slice(0, 6).map((m) => ({
      model: m.model_id,
      win_rate: m.win_rate,
    }));

    const leaderboard = {
      width: "container",
      height: 280,
      data: { values: top },
      mark: "bar",
      encoding: {
        y: { field: "model", type: "nominal", sort: "-x" },
        x: { field: "win_rate", type: "quantitative", axis: { format: ".0%" } },
        color: { field: "win_rate", type: "quantitative", scale: { scheme: "blues" } },
      },
    };

    const side = derived.modelStats.map((m) => ({
      model: m.model_id,
      gap: m.pro_win_rate - m.con_win_rate,
      pro: m.pro_win_rate,
      con: m.con_win_rate,
    }));
    side.sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap));
    const sideBias = {
      width: "container",
      height: 280,
      data: { values: side },
      mark: "bar",
      encoding: {
        x: { field: "gap", type: "quantitative", axis: { format: ".0%" } },
        y: { field: "model", type: "nominal", sort: "-x" },
        color: { field: "gap", type: "quantitative", scale: { scheme: "purpleorange" } },
      },
    };

    const h2h = {
      width: "container",
      height: 320,
      data: { values: derived.headToHead },
      mark: "rect",
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
    };

    const judgeHeat = {
      width: "container",
      height: 260,
      data: { values: derived.judgeAgreement },
      mark: "rect",
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
    };

    const categoryHeat = (() => {
      const rows = derived.topicWinrates.map((t) => ({
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
        mark: "rect",
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
      };
    })();

    return { leaderboard, sideBias, h2h, judgeHeat, categoryHeat };
  }, [derived]);
}

function NavTabs() {
  return (
    <div className="nav-tabs mb-5">
      <a href="#overview" className="nav-tab active">
        Overview
      </a>
    </div>
  );
}

export default function Home() {
  const { status, error, derived } = useEnsureData();
  const specs = useSpecs(derived);

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
    <main className="min-h-screen text-slate-50">
      <div className="container-page">
        <div className="nav-bar">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-[var(--accent)]/15 border border-[var(--accent)]/40 flex items-center justify-center text-sm font-bold text-[var(--accent)]">DB</div>
            <div>
              <p className="text-xs tracking-[0.28em] text-slate-400">DEBATEBENCH</p>
              <h1 className="text-3xl font-semibold text-white">Interactive Results Dashboard</h1>
              <p className="text-slate-400 text-sm">Balanced sample5 run • private S3 JSONL</p>
            </div>
          </div>
          <div className="pill">
            <span className="inline-block h-2 w-2 rounded-full bg-[var(--accent)]" />
            <span>{status === "ready" ? "Live" : status === "loading" ? "Loading" : "Idle"}</span>
          </div>
        </div>

        <NavTabs />

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
              <ChartCard title="Leaderboard (win rate)">
                {specs.leaderboard && <VegaLiteChart spec={specs.leaderboard} />}
              </ChartCard>
              <ChartCard title="Side bias (pro minus con win rate)">
                {specs.sideBias && <VegaLiteChart spec={specs.sideBias} />}
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
              <div className="hidden md:block" />
            </section>

            <section id="builder" className="grid gap-4 md:grid-cols-2">
              <div className="hidden md:block" />
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
    </main>
  );
}
