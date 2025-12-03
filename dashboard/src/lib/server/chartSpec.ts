import { VisualizationSpec } from "vega-embed";
import { DerivedData } from "@/lib/types";

export type DatasetKey = "debates" | "judges";
export type ChartType = "bar" | "scatter" | "heatmap";

export type DataRow = Record<string, string | number | null | undefined>;

export interface ChartRequest {
  dataset: DatasetKey;
  chartType: ChartType;
  xField: string;
  yField?: string;
  colorField?: string;
}

export function inferType(values: DataRow[], field: string): "quantitative" | "nominal" {
  const sample = values.find((v) => v[field] !== undefined && v[field] !== null);
  if (!sample) return "nominal";
  return typeof sample[field] === "number" ? "quantitative" : "nominal";
}

export function buildFields(data: DerivedData, dataset: DatasetKey): string[] {
  const rows = dataset === "debates" ? data.debateRows : data.judgeRows;
  if (!rows?.length) return [];
  const base = new Set(rows.flatMap((r) => Object.keys(r)));
  // ensure derived quantitative helper fields are available
  base.add("win_rate");
  return Array.from(base);
}

export function buildFieldTypes(rows: DataRow[]): Record<string, "quantitative" | "nominal"> {
  const types: Record<string, "quantitative" | "nominal"> = {};
  if (!rows.length) return types;
  for (const field of Object.keys(rows[0])) {
    types[field] = inferType(rows, field);
  }
  // force helper fields
  types["win_rate"] = "quantitative";
  return types;
}

export function buildChartSpec(rows: DataRow[], req: ChartRequest): VisualizationSpec | null {
  if (!rows.length || !req.xField) return null;
  if (req.chartType === "scatter" && !req.yField) return null;
  const xType = inferType(rows, req.xField);
  const yType = req.yField ? inferType(rows, req.yField) : "nominal";

  const markByType: Record<ChartType, { type: "bar" | "point" | "rect" }> = {
    bar: { type: "bar" },
    scatter: { type: "point" },
    heatmap: { type: "rect" },
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

  let dataRows: DataRow[] = rows;

  if (req.chartType === "heatmap") {
    enc.y = { field: req.yField || req.xField, type: yType };
    const colorField = req.colorField || req.yField || req.xField;
    let workingRows = rows;
    // Derive win_rate if requested and missing
    if (colorField === "win_rate") {
      workingRows = rows.map((r) => {
        const winner = r.winner as string | null;
        const winRate = winner === "pro" ? 1 : winner === "con" ? 0 : 0.5;
        return { ...r, win_rate: winRate };
      });
    }
    const colorType = inferType(workingRows, colorField);
    enc.color =
      colorType === "quantitative"
        ? { field: colorField, type: "quantitative", aggregate: "mean", title: colorField }
        : { aggregate: "count", type: "quantitative" };

    // Tooltips for heatmap
    enc.tooltip = [
      { field: req.xField, type: xType, title: req.xField },
      { field: req.yField || req.xField, type: yType, title: req.yField || req.xField },
      colorType === "quantitative"
        ? { field: colorField, type: "quantitative", title: colorField, aggregate: "mean" }
        : { aggregate: "count", type: "quantitative", title: "count" },
    ];

    dataRows = workingRows;
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

    // Tooltips for bar
    const barTips: Array<Record<string, unknown>> = [
      { field: req.xField, type: xType, title: req.xField },
    ];
    const encY = enc.y as { field?: string; aggregate?: string } | undefined;
    if (encY && encY.field) {
      barTips.push({
        field: encY.field,
        type: yType,
        title: encY.field,
        aggregate: encY.aggregate,
      });
    } else {
      barTips.push({ aggregate: "count", type: "quantitative", title: "count" });
    }
    if (req.colorField) {
      barTips.push({ field: req.colorField, type: inferType(rows, req.colorField), title: req.colorField });
    }
    enc.tooltip = barTips;
  }

  const baseSpec: VisualizationSpec = {
    width: "container",
    height: 360,
    data: { values: dataRows },
    mark: markByType[req.chartType],
    encoding: enc,
    autosize: { type: "fit", contains: "padding" },
    background: "transparent",
    view: { stroke: "transparent", fill: "transparent" },
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
