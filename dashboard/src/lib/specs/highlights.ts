import { DerivedData } from "@/lib/types";
import { VisualizationSpec } from "vega-embed";
import { accentRange, heatRange } from "@/lib/vegaTheme";

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
