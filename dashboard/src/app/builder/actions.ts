"use server";

import { VisualizationSpec } from "vega-embed";
import { getMetrics } from "@/lib/server/metrics";
import {
  buildChartSpec,
  buildFields,
  ChartRequest,
  DatasetKey,
  buildFieldTypes,
} from "@/lib/server/chartSpec";
import { chooseModels, filterRowsByModels, parseCompareParam } from "./shared";
import { pickOrFallback } from "@/lib/server/validate";

export type BuildChartResponse = {
  spec: VisualizationSpec | null;
  fields: string[];
  fieldTypes: Record<string, "quantitative" | "nominal">;
  selectedModels: string[];
};

export async function buildChart(
  formData: FormData,
): Promise<BuildChartResponse> {
  const dataset = pickOrFallback<DatasetKey>(
    formData.get("dataset"),
    ["debates", "judges"],
    "debates",
  );
  const chartType = pickOrFallback<ChartRequest["chartType"]>(
    formData.get("chartType"),
    ["bar", "scatter", "heatmap"],
    "bar",
  );
  const xField = (formData.get("xField") as string) || "";
  const yField = (formData.get("yField") as string) || undefined;
  const colorField = (formData.get("colorField") as string) || undefined;
  const runId = (formData.get("run") as string) || undefined;

  const modelsRaw = formData.getAll("models");
  const requested = parseCompareParam(modelsRaw as string[]);

  const metrics = await getMetrics(false, runId, undefined, {
    includeRows: true,
  });
  const derived = metrics.derived;
  const selectedModels = chooseModels(derived, requested);
  const rows = filterRowsByModels(derived, selectedModels, dataset);
  const fields = buildFields(derived, dataset);
  const fieldTypes = buildFieldTypes(rows);

  const safeX = fields.includes(xField) ? xField : fields[0] || "";
  const safeY = yField && fields.includes(yField) ? yField : undefined;
  const safeColor =
    colorField && fields.includes(colorField) ? colorField : undefined;

  const req: ChartRequest = {
    dataset,
    chartType,
    xField: safeX,
    yField: safeY,
    colorField: safeColor,
  };

  const spec = buildChartSpec(rows, req);

  return { spec, fields, fieldTypes, selectedModels };
}
