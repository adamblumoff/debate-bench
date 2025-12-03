import { VisualizationSpec } from "vega-embed";
import { DerivedData } from "@/lib/types";

export type DatasetKey = "debates" | "judges";
export type ChartType = "bar" | "scatter" | "heatmap" | "boxplot";

export type DataRow = Record<string, string | number | null | undefined>;

export interface ChartRequest {
  dataset: DatasetKey;
  chartType: ChartType;
  xField: string;
  yField?: string;
  colorField?: string;
}

function inferType(values: DataRow[], field: string): "quantitative" | "nominal" {
  const sample = values.find((v) => v[field] !== undefined && v[field] !== null);
  if (!sample) return "nominal";
  return typeof sample[field] === "number" ? "quantitative" : "nominal";
}

export function buildFields(data: DerivedData, dataset: DatasetKey): string[] {
  const rows = dataset === "debates" ? data.debateRows : data.judgeRows;
  if (!rows?.length) return [];
  return Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
}

export function buildChartSpec(rows: DataRow[], req: ChartRequest): VisualizationSpec | null {
  if (!rows.length || !req.xField) return null;
  const xType = inferType(rows, req.xField);
  const yType = req.yField ? inferType(rows, req.yField) : "nominal";

  const markByType: Record<ChartType, string> = {
    bar: "bar",
    scatter: "point",
    heatmap: "rect",
    boxplot: "boxplot",
  };

  const enc: Record<string, unknown> = {
    x: { field: req.xField, type: xType, sort: "-y" },
  };

  if (req.chartType === "heatmap") {
    enc.y = { field: req.yField || req.xField, type: yType };
    enc.color = { aggregate: "count", type: "quantitative" };
  } else if (req.chartType === "boxplot") {
    enc.y = { field: req.yField, type: yType };
    if (req.colorField) enc.color = { field: req.colorField, type: inferType(rows, req.colorField) };
  } else if (req.chartType === "scatter") {
    enc.y = { field: req.yField, type: yType };
    if (req.colorField) enc.color = { field: req.colorField, type: inferType(rows, req.colorField) };
    enc.tooltip = [req.xField, req.yField, req.colorField]
      .filter(Boolean)
      .map((f) => ({ field: f!, type: inferType(rows, f!) }));
  } else {
    // bar
    if (req.yField) {
      const yEnc: Record<string, unknown> = { field: req.yField, type: yType };
      if (yType === "quantitative") yEnc.aggregate = "mean";
      enc.y = yEnc;
    } else {
      enc.y = { aggregate: "count", type: "quantitative" };
    }
    if (req.colorField) enc.color = { field: req.colorField, type: inferType(rows, req.colorField) };
  }

  return {
    width: "container",
    height: 360,
    data: { values: rows },
    mark: markByType[req.chartType],
    encoding: enc,
    autosize: { type: "fit", contains: "padding" },
  };
}
