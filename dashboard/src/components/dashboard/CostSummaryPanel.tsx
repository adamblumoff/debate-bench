"use client";

import { useMemo } from "react";
import { VisualizationSpec } from "vega-embed";
import { ChartCard } from "@/components/ChartCard";
import { VegaLiteChart } from "@/components/VegaLiteChart";
import { PricingSnapshot } from "@/lib/pricing";
import { CostSummary } from "@/lib/types";

function fmtUsd(v: number): string {
  if (!Number.isFinite(v)) return "$0.00";
  const abs = Math.abs(v);
  const digits = abs >= 1 ? 2 : 3;
  return `$${v.toFixed(digits)}`;
}

function fmtPct(v: number): string {
  if (!Number.isFinite(v)) return "0.0%";
  return `${(v * 100).toFixed(1)}%`;
}

function shortId(id: string): string {
  if (id.length <= 12) return id;
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

function buildCostTrendSpec(costSummary: CostSummary): VisualizationSpec {
  return {
    width: "container",
    height: 220,
    data: { values: costSummary.debates },
    layer: [
      {
        mark: { type: "line", strokeWidth: 2.2 },
        encoding: {
          x: {
            field: "seq",
            type: "quantitative",
            axis: { title: `Debates (n=${costSummary.debateCount})` },
          },
          y: {
            field: "total_cost_usd",
            type: "quantitative",
            axis: { title: "USD" },
            scale: { zero: true, nice: true },
          },
          tooltip: [
            { field: "seq", title: "#" },
            { field: "pro_model_id", title: "Pro" },
            { field: "con_model_id", title: "Con" },
            { field: "category", title: "Category" },
            { field: "motion", title: "Motion" },
            {
              field: "debater_cost_usd",
              title: "Debaters (USD)",
              format: ".4f",
            },
            { field: "judge_cost_usd", title: "Judges (USD)", format: ".4f" },
            { field: "total_cost_usd", title: "Total (USD)", format: ".4f" },
          ],
        },
      },
      {
        mark: { type: "point", filled: true, size: 42, opacity: 0.9 },
        encoding: {
          x: { field: "seq", type: "quantitative" },
          y: { field: "total_cost_usd", type: "quantitative" },
          tooltip: [
            { field: "seq", title: "#" },
            { field: "pro_model_id", title: "Pro" },
            { field: "con_model_id", title: "Con" },
            { field: "total_cost_usd", title: "Total (USD)", format: ".4f" },
          ],
        },
      },
    ],
  } satisfies VisualizationSpec;
}

function buildSpendByModelSpec(costSummary: CostSummary): VisualizationSpec {
  const top = costSummary.models.slice(0, 10);
  const values = top.flatMap((m) => [
    {
      model_id: m.model_id,
      kind: "debater",
      cost_usd: m.debater_cost_usd,
      total_cost_usd: m.total_cost_usd,
    },
    {
      model_id: m.model_id,
      kind: "judge",
      cost_usd: m.judge_cost_usd,
      total_cost_usd: m.total_cost_usd,
    },
  ]);
  return {
    width: "container",
    height: 220,
    data: { values },
    mark: { type: "bar", cornerRadiusEnd: 6 },
    encoding: {
      y: {
        field: "model_id",
        type: "nominal",
        sort: { field: "total_cost_usd", order: "descending" },
        axis: { title: "" },
      },
      x: {
        field: "cost_usd",
        type: "quantitative",
        axis: { title: "USD" },
        scale: { zero: true, nice: true },
      },
      color: {
        field: "kind",
        type: "nominal",
        scale: { domain: ["debater", "judge"], range: ["#6fe1ff", "#1f7aad"] },
        legend: { title: "" },
      },
      tooltip: [
        { field: "model_id", title: "Model" },
        { field: "kind", title: "Role" },
        { field: "cost_usd", title: "USD", format: ".4f" },
      ],
    },
  } satisfies VisualizationSpec;
}

export function CostSummaryPanel({
  costSummary,
  pricing,
}: {
  costSummary?: CostSummary;
  pricing: PricingSnapshot;
}) {
  const summary = costSummary;

  const trendSpec = useMemo(
    () => (summary ? buildCostTrendSpec(summary) : null),
    [summary],
  );
  const byModelSpec = useMemo(
    () => (summary ? buildSpendByModelSpec(summary) : null),
    [summary],
  );

  if (!summary || summary.debateCount === 0) {
    return (
      <div className="card highlight-card snapshot-card flex flex-col">
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
    );
  }

  const totals = summary.totals;
  const judgeShare =
    totals.total_cost_usd > 0
      ? totals.judge_cost_usd / totals.total_cost_usd
      : 0;
  const topStages = summary.stages.slice(0, 3);

  const expensive = [...summary.debates]
    .sort((a, b) => b.total_cost_usd - a.total_cost_usd)
    .slice(0, 8);

  const warnEstimated =
    summary.warnings?.estimated_judge_costs ||
    summary.warnings?.missing_judge_costs;

  return (
    <div className="space-y-3">
      {warnEstimated && (
        <div className="card highlight-card border border-amber-300/40 bg-amber-200/10 text-amber-100">
          <p className="text-xs">
            Judge costs are estimated from token counts and pricing when
            provider usage data is missing. Totals may differ from
            OpenRouter-reported costs.
          </p>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="card highlight-card">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
            Total spend
          </p>
          <div className="mt-2 flex items-baseline justify-between gap-3">
            <div className="text-xl font-semibold text-white">
              {fmtUsd(totals.total_cost_usd)}
            </div>
            <div className="pill">{`All ${summary.debateCount}`}</div>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Debaters {fmtUsd(totals.debater_cost_usd)} • Judges{" "}
            {fmtUsd(totals.judge_cost_usd)} ({fmtPct(judgeShare)})
          </p>
        </div>
        <div className="card highlight-card">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
            Per-debate cost
          </p>
          <div className="mt-2 text-xl font-semibold text-white">
            {fmtUsd(summary.per_debate.mean_cost_usd)}{" "}
            <span className="text-xs font-normal text-slate-400">mean</span>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Median {fmtUsd(summary.per_debate.median_cost_usd)} • P90{" "}
            {fmtUsd(summary.per_debate.p90_cost_usd)}
          </p>
        </div>
        <div className="card highlight-card">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
            Stage spend
          </p>
          <div className="mt-2 text-xl font-semibold text-white">
            {topStages.length ? topStages[0].stage : "—"}
          </div>
          <p className="text-xs text-slate-500 mt-2">
            {topStages.length
              ? topStages
                  .map((s) => `${s.stage} ${fmtUsd(s.cost_usd)}`)
                  .join(" • ")
              : "No stage cost data"}
          </p>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <ChartCard
          title="Cost trend"
          subtitle={`Total cost per debate (${summary.currency})`}
          className="chart-card highlight-card h-full"
        >
          {trendSpec && <VegaLiteChart spec={trendSpec} />}
        </ChartCard>
        <ChartCard
          title="Spend by model"
          subtitle={`Top 10 by total spend (debater vs judge)`}
          className="chart-card highlight-card h-full"
        >
          {byModelSpec && <VegaLiteChart spec={byModelSpec} />}
        </ChartCard>
      </div>

      <div className="card highlight-card">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
              Most expensive debates
            </p>
            <p className="text-xs text-slate-500">
              Top 8 by total cost (n={summary.debateCount})
            </p>
          </div>
          <a href="#pricing" className="btn-ghost">
            Pricing table
          </a>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="py-2 pr-4 text-left">Debate</th>
                <th className="py-2 pr-4 text-left">Matchup</th>
                <th className="py-2 pr-4 text-left">Topic</th>
                <th className="py-2 pr-4 text-right">Total</th>
                <th className="py-2 pr-4 text-right">Judge share</th>
              </tr>
            </thead>
            <tbody className="text-slate-200">
              {expensive.map((d) => (
                <tr
                  key={d.debate_id}
                  className="border-t border-[var(--border)]/60"
                >
                  <td
                    className="py-2 pr-4 text-slate-400 whitespace-nowrap"
                    title={d.debate_id}
                  >
                    {shortId(d.debate_id)}
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap">
                    <span className="text-slate-200">{d.pro_model_id}</span>{" "}
                    <span className="text-slate-500">vs</span>{" "}
                    <span className="text-slate-200">{d.con_model_id}</span>
                  </td>
                  <td className="py-2 pr-4 text-slate-400 max-w-[420px] truncate">
                    {d.motion || d.topic_id}
                  </td>
                  <td className="py-2 pr-4 text-right whitespace-nowrap">
                    {fmtUsd(d.total_cost_usd)}
                  </td>
                  <td className="py-2 pr-4 text-right whitespace-nowrap text-slate-400">
                    {fmtPct(
                      d.total_cost_usd > 0
                        ? d.judge_cost_usd / d.total_cost_usd
                        : 0,
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
