import { DerivedData } from "@/lib/types";
import { PricingSnapshot } from "@/lib/pricing";
import { VisualizationSpec } from "vega-embed";
import { accentRange, heatRange } from "@/lib/vegaTheme";

export type PricePerfMetric = "elo" | "win_rate";

export function buildLeaderboardSpec(
  derived: DerivedData,
  limit: number,
): VisualizationSpec {
  const topStats = derived.modelStats.slice(0, limit);
  const x = {
    field: "rating",
    type: "quantitative" as const,
    axis: { title: "Elo" },
    scale: { zero: true, nice: true },
  };
  const y = {
    field: "model_id",
    type: "nominal" as const,
    sort: { field: "rating", order: "descending" as const },
  };
  return {
    width: "container",
    height: 260,
    data: { values: topStats },
    layer: [
      {
        mark: { type: "bar", cornerRadiusEnd: 6 },
        encoding: {
          y,
          x,
          color: {
            field: "rating",
            type: "quantitative",
            scale: { range: accentRange },
          },
          tooltip: [
            { field: "model_id", title: "Model" },
            { field: "rating", title: "Elo", format: ".0f" },
            { field: "win_rate", title: "Win rate", format: ".1%" },
          ],
        },
      },
      {
        mark: {
          type: "text",
          align: "left",
          baseline: "middle",
          dx: 6,
          fill: "#d9f7ff",
          fontSize: 11,
        },
        encoding: {
          y,
          x,
          text: { field: "rating", format: ".0f" },
          color: { value: "#d9f7ff" },
        },
      },
    ],
  } satisfies VisualizationSpec;
}

export function buildWinrateSpec(
  derived: DerivedData,
  limit: number,
): VisualizationSpec {
  const topWin = [...derived.modelStats]
    .sort((a, b) => b.win_rate - a.win_rate)
    .slice(0, limit);
  const x = {
    field: "win_rate",
    type: "quantitative" as const,
    axis: { format: ".0%", title: "Win rate" },
    scale: { zero: true, nice: true, domain: [0, 1] },
  };
  const y = {
    field: "model_id",
    type: "nominal" as const,
    sort: { field: "win_rate", order: "descending" as const },
  };
  return {
    width: "container",
    height: 260,
    data: { values: topWin },
    layer: [
      {
        mark: { type: "bar", cornerRadiusEnd: 6 },
        encoding: {
          y,
          x,
          color: {
            field: "win_rate",
            type: "quantitative",
            scale: { range: accentRange },
          },
          tooltip: [
            { field: "model_id", title: "Model" },
            { field: "win_rate", title: "Win rate", format: ".1%" },
            { field: "games", title: "Games", format: ".0f" },
          ],
        },
      },
      {
        mark: {
          type: "text",
          align: "left",
          baseline: "middle",
          dx: 6,
          fill: "#d9f7ff",
          fontSize: 11,
        },
        encoding: {
          y,
          x,
          text: { field: "win_rate", format: ".0%" },
          color: { value: "#d9f7ff" },
        },
      },
    ],
  } satisfies VisualizationSpec;
}

export function buildTokenStackSpec(
  derived: DerivedData,
  limit: number,
): VisualizationSpec {
  const tokenRows = derived.modelStats.slice(0, limit).flatMap((m) => [
    { model: m.model_id, kind: "prompt", tokens: m.mean_prompt_tokens },
    { model: m.model_id, kind: "output", tokens: m.mean_completion_tokens },
  ]);
  return {
    width: "container",
    height: 260,
    data: { values: tokenRows },
    mark: { type: "bar" },
    encoding: {
      y: {
        field: "model",
        type: "nominal" as const,
        sort: { field: "tokens", order: "descending" as const },
      },
      x: {
        field: "tokens",
        type: "quantitative",
        axis: { title: "Mean tokens" },
        scale: { zero: true, nice: true },
      },
      color: {
        field: "kind",
        type: "nominal",
        scale: { domain: ["prompt", "output"], range: ["#6fe1ff", "#1f7aad"] },
        legend: { title: "Tokens" },
      },
      tooltip: [
        { field: "model", title: "Model" },
        { field: "kind", title: "Type" },
        { field: "tokens", title: "Mean tokens", format: ".0f" },
      ],
    },
  } satisfies VisualizationSpec;
}

export function buildRatingVsWinSpec(derived: DerivedData): VisualizationSpec {
  return {
    width: "container",
    height: 260,
    data: { values: derived.modelStats },
    mark: { type: "point", filled: true, opacity: 0.92, size: 80 },
    encoding: {
      x: { field: "rating", type: "quantitative", axis: { title: "Elo" } },
      y: {
        field: "win_rate",
        type: "quantitative",
        axis: { title: "Win rate", format: ".0%" },
      },
      color: {
        field: "mean_total_tokens",
        type: "quantitative",
        scale: { range: heatRange },
        legend: { title: "Mean tokens" },
      },
      tooltip: [
        { field: "model_id", title: "Model" },
        { field: "rating", title: "Elo", format: ".0f" },
        { field: "win_rate", title: "Win rate", format: ".1%" },
        { field: "mean_total_tokens", title: "Mean tokens", format: ".0f" },
      ],
    },
  } satisfies VisualizationSpec;
}

export function buildPricePerfSpec(
  derived: DerivedData,
  pricing: PricingSnapshot,
  metric: PricePerfMetric,
): VisualizationSpec {
  const pricingMap = new Map(pricing.rows.map((r) => [r.model_id, r]));

  const values = derived.modelStats.flatMap((m) => {
    const totalTokens =
      (m.mean_prompt_tokens || 0) + (m.mean_completion_tokens || 0);
    if (!totalTokens) return [];

    let costPerMillion: number | null = null;
    let provider: string | undefined;

    if (typeof m.mean_cost_usd === "number" && m.mean_cost_usd > 0) {
      costPerMillion = (m.mean_cost_usd / totalTokens) * 1_000_000;
    } else {
      const pricingRow = pricingMap.get(m.model_id);
      if (pricingRow) {
        const prompt = m.mean_prompt_tokens || 0;
        const output = m.mean_completion_tokens || 0;
        const denom = prompt + output;
        if (denom > 0) {
          costPerMillion =
            (pricingRow.input_per_million * prompt +
              pricingRow.output_per_million * output) /
            denom;
        } else {
          costPerMillion =
            (pricingRow.input_per_million + pricingRow.output_per_million) / 2;
        }
        provider = pricingRow.provider;
      }
    }

    if (!costPerMillion || costPerMillion <= 0) return [];

    const ratioBase = metric === "win_rate" ? m.win_rate * 100 : m.rating;
    const ratio = ratioBase / costPerMillion;

    return [
      {
        model_id: m.model_id,
        rating: m.rating,
        win_rate: m.win_rate,
        games: m.games,
        cost_per_million: costPerMillion,
        cost_samples: m.cost_samples,
        provider,
        ratio,
      },
    ];
  });

  const yField = metric === "elo" ? "rating" : "win_rate";
  const yTitle = metric === "elo" ? "Elo" : "Win rate";
  const yFormat = metric === "elo" ? ".0f" : ".0%";
  const ratioTitle =
    metric === "elo" ? "Elo per $/1M" : "Win rate pts per $/1M";

  const costs = values.map((v) => v.cost_per_million).filter((v) => v > 0);
  const perfs = values
    .map((v) => (metric === "elo" ? v.rating : v.win_rate))
    .filter((v) => typeof v === "number" && Number.isFinite(v));

  const median = (nums: number[]) => {
    if (!nums.length) return null;
    const sorted = [...nums].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 0
      ? (sorted[mid - 1] + sorted[mid]) / 2
      : sorted[mid];
  };

  const xMin = Math.min(...costs);
  const xMax = Math.max(...costs);
  const yMin = Math.min(...perfs);
  const yMax = Math.max(...perfs);
  const xMid = median(costs);
  const yMid = median(perfs);

  const quadrantLayer =
    values.length &&
    xMid !== null &&
    yMid !== null &&
    Number.isFinite(xMin) &&
    Number.isFinite(xMax) &&
    Number.isFinite(yMin) &&
    Number.isFinite(yMax)
      ? [
          {
            data: {
              values: [
                { x0: xMin, x1: xMid, y0: yMid, y1: yMax, q: "best" },
                { x0: xMid, x1: xMax, y0: yMid, y1: yMax, q: "premium" },
                { x0: xMin, x1: xMid, y0: yMin, y1: yMid, q: "budget" },
                { x0: xMid, x1: xMax, y0: yMin, y1: yMid, q: "overpriced" },
              ],
            },
            mark: { type: "rect", opacity: 0.18 },
            encoding: {
              x: { field: "x0", type: "quantitative" },
              x2: { field: "x1" },
              y: { field: "y0", type: "quantitative" },
              y2: { field: "y1" },
              color: {
                field: "q",
                type: "nominal",
                scale: {
                  domain: ["best", "premium", "budget", "overpriced"],
                  range: ["#6fe1ff", "#5777ff", "#46d29a", "#ff8f6b"],
                },
                legend: null,
              },
            },
          },
          {
            data: {
              values: [
                { x: xMid, y0: yMin, y1: yMax },
              ],
            },
            mark: { type: "rule", strokeDash: [6, 6], strokeWidth: 1.5, opacity: 0.6 },
            encoding: {
              x: { field: "x", type: "quantitative" },
              y: { field: "y0", type: "quantitative" },
              y2: { field: "y1" },
              color: { value: "#7cc0ff" },
            },
          },
          {
            data: {
              values: [
                { y: yMid, x0: xMin, x1: xMax },
              ],
            },
            mark: { type: "rule", strokeDash: [6, 6], strokeWidth: 1.5, opacity: 0.6 },
            encoding: {
              y: { field: "y", type: "quantitative" },
              x: { field: "x0", type: "quantitative" },
              x2: { field: "x1" },
              color: { value: "#7cc0ff" },
            },
          },
        ]
      : [];

  const quadrantLabels =
    values.length &&
    xMid !== null &&
    yMid !== null &&
    Number.isFinite(xMin) &&
    Number.isFinite(xMax) &&
    Number.isFinite(yMin) &&
    Number.isFinite(yMax)
      ? [
          {
            data: {
              values: [
                {
                  x: (xMin + xMid) / 2,
                  y: (yMid + yMax) / 2,
                  label: "Best value",
                },
                {
                  x: (xMid + xMax) / 2,
                  y: (yMid + yMax) / 2,
                  label: "Premium",
                },
                {
                  x: (xMin + xMid) / 2,
                  y: (yMin + yMid) / 2,
                  label: "Budget",
                },
                {
                  x: (xMid + xMax) / 2,
                  y: (yMin + yMid) / 2,
                  label: "Overpriced",
                },
              ],
            },
            mark: {
              type: "text",
              fontSize: 13,
              fontWeight: 700,
              opacity: 0.95,
              stroke: "#0b141c",
              strokeWidth: 3,
            },
            encoding: {
              x: { field: "x", type: "quantitative" },
              y: { field: "y", type: "quantitative" },
              text: { field: "label" },
              color: { value: "#0b141c" },
            },
          },
          {
            data: {
              values: [
                {
                  x: (xMin + xMid) / 2,
                  y: (yMid + yMax) / 2,
                  label: "Best value",
                },
                {
                  x: (xMid + xMax) / 2,
                  y: (yMid + yMax) / 2,
                  label: "Premium",
                },
                {
                  x: (xMin + xMid) / 2,
                  y: (yMin + yMid) / 2,
                  label: "Budget",
                },
                {
                  x: (xMid + xMax) / 2,
                  y: (yMin + yMid) / 2,
                  label: "Overpriced",
                },
              ],
            },
            mark: {
              type: "text",
              fontSize: 13,
              fontWeight: 700,
              opacity: 0.95,
            },
            encoding: {
              x: { field: "x", type: "quantitative" },
              y: { field: "y", type: "quantitative" },
              text: { field: "label" },
              color: { value: "#e9eef7" },
            },
          },
        ]
      : [];

  return {
    width: "container",
    height: 320,
    data: { values },
    layer: [
      ...quadrantLayer,
      {
        mark: {
          type: "point",
          filled: true,
          opacity: 0.98,
          size: 120,
          stroke: "#0b141c",
          strokeWidth: 1.4,
        },
        encoding: {
          x: {
            field: "cost_per_million",
            type: "quantitative",
            axis: { title: "USD / 1M tokens", format: "$.2f" },
            scale: { nice: true, zero: false, type: "log" },
          },
          y: {
            field: yField,
            type: "quantitative",
            axis: { title: yTitle, format: yFormat },
            scale: { nice: true, zero: false },
          },
          color: { value: "#c7f1ff" },
          tooltip: [
            { field: "model_id", title: "Model" },
            { field: "cost_per_million", title: "USD / 1M", format: "$.2f" },
            { field: yField, title: yTitle, format: yFormat },
            { field: "ratio", title: ratioTitle, format: ".2f" },
            { field: "cost_samples", title: "Cost samples" },
          ],
        },
      },
      ...quadrantLabels,
    ],
  } satisfies VisualizationSpec;
}
