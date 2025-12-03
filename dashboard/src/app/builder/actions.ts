"use server";

import { VisualizationSpec } from "vega-embed";
import { getMetrics } from "@/lib/server/metrics";
import { buildChartSpec, buildFields, ChartRequest, DatasetKey, buildFieldTypes } from "@/lib/server/chartSpec";
import { chooseModels, filterRowsByModels, parseCompareParam } from "./shared";

export type BuildChartResponse = {
  spec: VisualizationSpec | null;
  fields: string[];
  fieldTypes: Record<string, "quantitative" | "nominal">;
  selectedModels: string[];
};

export async function buildChart(formData: FormData): Promise<BuildChartResponse> {
  const dataset = (formData.get("dataset") as DatasetKey) || "debates";
  const chartType = (formData.get("chartType") as ChartRequest["chartType"]) || "bar";
  const xField = (formData.get("xField") as string) || "";
  const yField = (formData.get("yField") as string) || undefined;
  const colorField = (formData.get("colorField") as string) || undefined;

  const modelsRaw = formData.getAll("models");
  const requested = parseCompareParam(modelsRaw as string[]);

  const metrics = await getMetrics(false);
  const derived = metrics.derived;
  const selectedModels = chooseModels(derived, requested);
  const rows = filterRowsByModels(derived, selectedModels, dataset);
  const fields = buildFields(derived, dataset);
    const fieldTypes = buildFieldTypes(rows);

  const req: ChartRequest = {
    dataset,
    chartType,
    xField,
    yField,
    colorField,
  };

  const spec = buildChartSpec(rows, req);

  return { spec, fields, fieldTypes, selectedModels };
}
