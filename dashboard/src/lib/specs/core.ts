import { DerivedData } from "@/lib/types";
import { VisualizationSpec } from "vega-embed";
import { divergingRange, heatRange } from "@/lib/vegaTheme";

export function buildSideBiasSpec(
  derived: DerivedData,
  limit: number,
): VisualizationSpec {
  const side = derived.modelStats.map((m) => ({
    model: m.model_id,
    gap: m.pro_win_rate - m.con_win_rate,
    pro: m.pro_win_rate,
    con: m.con_win_rate,
  }));
  side.sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap));
  return {
    width: "container",
    height: 260,
    data: { values: side.slice(0, limit + 2) },
    mark: { type: "bar" },
    encoding: {
      x: { field: "gap", type: "quantitative", axis: { format: ".0%" } },
      y: { field: "model", type: "nominal", sort: "-x" },
      color: {
        field: "gap",
        type: "quantitative",
        scale: { range: divergingRange },
      },
    },
  } satisfies VisualizationSpec;
}

export function buildH2HSpec(derived: DerivedData): VisualizationSpec {
  return {
    width: "container",
    height: 320,
    data: { values: derived.headToHead },
    mark: { type: "rect" },
    encoding: {
      x: { field: "col", type: "nominal" },
      y: { field: "row", type: "nominal" },
      color: {
        field: "win_rate",
        type: "quantitative",
        scale: { range: heatRange, domain: [0, 1] },
        legend: { format: ".0%" },
      },
      tooltip: [
        { field: "row", type: "nominal", title: "row" },
        { field: "col", type: "nominal", title: "col" },
        {
          field: "win_rate",
          type: "quantitative",
          title: "win %",
          format: ".1%",
        },
        { field: "samples", type: "quantitative", title: "n" },
      ],
    },
    config: { axis: { labelAngle: -45 } },
  } satisfies VisualizationSpec;
}

export function buildJudgeHeatSpec(derived: DerivedData): VisualizationSpec {
  return {
    width: "container",
    height: 260,
    data: { values: derived.judgeAgreement },
    mark: { type: "rect" },
    encoding: {
      x: { field: "judge_a", type: "nominal" },
      y: { field: "judge_b", type: "nominal" },
      color: {
        field: "agreement_rate",
        type: "quantitative",
        scale: { range: heatRange, domain: [0, 1] },
        legend: { format: ".0%" },
      },
      tooltip: [
        { field: "judge_a", type: "nominal" },
        { field: "judge_b", type: "nominal" },
        { field: "agreement_rate", type: "quantitative", format: ".1%" },
        { field: "samples", type: "quantitative" },
      ],
    },
    config: { axis: { labelAngle: -30 } },
  } satisfies VisualizationSpec;
}

export function buildCategoryHeatSpec(
  derived: DerivedData,
  category: string,
): VisualizationSpec {
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
      color: {
        field: "win_rate",
        type: "quantitative",
        scale: { range: heatRange, domain: [0, 1] },
        legend: { format: ".0%" },
      },
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
}
