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
  if ((req.chartType === "scatter" || req.chartType === "boxplot") && !req.yField) return null;
  const xType = inferType(rows, req.xField);
  const yType = req.yField ? inferType(rows, req.yField) : "nominal";

  const markByType: Record<ChartType, { type: "bar" | "point" | "rect" | "boxplot" }> = {
    bar: { type: "bar" },
    scatter: { type: "point" },
    heatmap: { type: "rect" },
    boxplot: { type: "boxplot" },
  };

  const enc: Record<string, unknown> = {
    x: {
      field: req.xField,
      type: xType,
      axis: xType === "nominal" ? { labelAngle: -25 } : undefined,
    },
  };
  if (req.yField) {
    const xEnc = enc.x as { field: string; type: string; sort?: string; axis?: unknown };
    xEnc.sort = "-y";
    enc.x = xEnc;
  }

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

  const baseSpec: VisualizationSpec = {
    width: "container",
    height: 360,
    data: { values: rows },
    mark: markByType[req.chartType],
    encoding: enc,
    autosize: { type: "fit", contains: "padding" },
  };

  // Add value labels for bar charts
  if (req.chartType === "bar") {
    const yEnc = enc.y as Record<string, unknown> | undefined;
    let textEncoding: Record<string, unknown> | null = null;
    if (yEnc) {
      const aggregate = yEnc.aggregate as string | undefined;
      const textField = (yEnc.field as string | undefined) ?? "*";
      textEncoding = {
        x: enc.x,
        y: enc.y,
        text: {
          field: textField,
          aggregate: aggregate,
          type: "quantitative",
          format: ".2~f",
        },
        color: { value: "#e9eef7" },
      };
    } else {
      textEncoding = {
        x: enc.x,
        y: { aggregate: "count", type: "quantitative" },
        text: { aggregate: "count", type: "quantitative", format: ".0f" },
        color: { value: "#e9eef7" },
      };
    }
    return {
      ...baseSpec,
      layer: [
        { mark: markByType.bar, encoding: enc },
        {
          mark: { type: "text", dy: -6 },
          encoding: textEncoding ?? {},
          transform: [
            {
              filter: {
                or: [
                  { field: "value", gte: 4 },
                  { field: "count_*", gte: 4 },
                ],
              },
            },
          ],
        },
      ],
    };
  }

  return baseSpec;
}
