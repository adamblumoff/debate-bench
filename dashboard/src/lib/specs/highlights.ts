import { DerivedData } from "@/lib/types";
import { VisualizationSpec } from "vega-embed";
import { accentRange, heatRange } from "@/lib/vegaTheme";

export function buildLeaderboardSpec(
  derived: DerivedData,
  limit: number,
): VisualizationSpec {
  const topStats = derived.modelStats.slice(0, limit);
  return {
    width: "container",
    height: 260,
    data: { values: topStats },
    mark: { type: "bar" },
    encoding: {
      y: { field: "model_id", type: "nominal", sort: "-x" },
      x: { field: "rating", type: "quantitative", axis: { title: "Elo" } },
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
  } satisfies VisualizationSpec;
}

export function buildWinrateSpec(
  derived: DerivedData,
  limit: number,
): VisualizationSpec {
  const topWin = [...derived.modelStats]
    .sort((a, b) => b.win_rate - a.win_rate)
    .slice(0, limit);
  return {
    width: "container",
    height: 260,
    data: { values: topWin },
    mark: { type: "bar" },
    encoding: {
      y: { field: "model_id", type: "nominal", sort: "-x" },
      x: {
        field: "win_rate",
        type: "quantitative",
        axis: { format: ".0%", title: "Win rate" },
      },
      color: {
        field: "win_rate",
        type: "quantitative",
        scale: { range: accentRange },
      },
    },
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
      y: { field: "model", type: "nominal", sort: "-x" },
      x: {
        field: "tokens",
        type: "quantitative",
        axis: { title: "Mean tokens" },
      },
      color: {
        field: "kind",
        type: "nominal",
        scale: { domain: ["prompt", "output"], range: ["#6fe1ff", "#1f7aad"] },
        legend: { title: "Tokens" },
      },
    },
  } satisfies VisualizationSpec;
}

export function buildRatingVsWinSpec(derived: DerivedData): VisualizationSpec {
  return {
    width: "container",
    height: 260,
    data: { values: derived.modelStats },
    mark: { type: "point" },
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
