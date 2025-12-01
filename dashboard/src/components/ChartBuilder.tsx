"use client";

import { useMemo, useState } from "react";
import { DerivedData } from "@/lib/types";
import { VisualizationSpec } from "vega-embed";
import { VegaLiteChart } from "./VegaLiteChart";

const chartTypes = ["bar", "scatter", "heatmap", "boxplot"] as const;
type ChartType = (typeof chartTypes)[number];

type DatasetKey = "debates" | "judges";
type DataRow = Record<string, string | number | null | undefined>;

function inferType(values: DataRow[], field: string): "quantitative" | "nominal" {
  const sample = values.find((v) => v[field] !== undefined);
  if (sample == null) return "nominal";
  const val = sample[field];
  return typeof val === "number" ? "quantitative" : "nominal";
}

export function ChartBuilder({ data }: { data: DerivedData }) {
  const datasets = useMemo<Record<DatasetKey, DataRow[]>>(
    () => ({
      debates: data.debateRows as DataRow[],
      judges: data.judgeRows as DataRow[],
    }),
    [data.debateRows, data.judgeRows]
  );

  const [datasetKey, setDatasetKey] = useState<DatasetKey>("debates");
  const [chartType, setChartType] = useState<ChartType>("bar");
  const [xField, setXField] = useState<string>("pro_model_id");
  const [yField, setYField] = useState<string>("winner");
  const [colorField, setColorField] = useState<string | "">("");

  const fields = useMemo(() => {
    const rows = datasets[datasetKey];
    if (!rows?.length) return [] as string[];
    return Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  }, [datasetKey, datasets]);

  const spec: VisualizationSpec | null = useMemo(() => {
    const rows = datasets[datasetKey];
    if (!rows?.length || !xField) return null;
    const xType = inferType(rows, xField);
    const yType = yField ? inferType(rows, yField) : "nominal";
    const markByType: Record<ChartType, VisualizationSpec["mark"]> = {
      bar: { type: "bar" },
      scatter: { type: "point", tooltip: true },
      heatmap: { type: "rect" },
      boxplot: { type: "boxplot" },
    };
    const enc: Record<string, unknown> = {
      x: { field: xField, type: xType, sort: "-y" },
    };
    if (chartType === "heatmap") {
      enc.y = { field: yField || xField, type: yType };
      enc.color = { aggregate: "count", type: "quantitative" };
    } else if (chartType === "boxplot") {
      enc.y = { field: yField, type: yType };
      if (colorField) enc.color = { field: colorField, type: inferType(rows, colorField) };
    } else if (chartType === "scatter") {
      enc.y = { field: yField, type: yType };
      if (colorField) enc.color = { field: colorField, type: inferType(rows, colorField) };
      enc.tooltip = [xField, yField, colorField].filter(Boolean).map((f) => ({ field: f!, type: inferType(rows, f!) }));
    } else {
      // bar
      if (yField) {
        enc.y = { field: yField, type: yType, aggregate: yType === "quantitative" ? "mean" : undefined };
      } else {
        enc.y = { aggregate: "count", type: "quantitative" };
      }
      if (colorField) enc.color = { field: colorField, type: inferType(rows, colorField) };
    }

    return {
      width: "container",
      height: 320,
      data: { values: rows },
      mark: markByType[chartType],
      encoding: enc,
      autosize: { type: "fit", contains: "padding" },
    } satisfies VisualizationSpec;
  }, [datasets, datasetKey, xField, yField, colorField, chartType]);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-sm text-zinc-600 dark:text-zinc-300">
          Dataset
          <select
            className="mt-1 w-full rounded-md border border-zinc-200 bg-white p-2 text-sm dark:border-zinc-800 dark:bg-zinc-900"
            value={datasetKey}
            onChange={(e) => setDatasetKey(e.target.value as DatasetKey)}
          >
            <option value="debates">Debates</option>
            <option value="judges">Judges</option>
          </select>
        </label>
        <label className="text-sm text-zinc-600 dark:text-zinc-300">
          Chart type
          <select
            className="mt-1 w-full rounded-md border border-zinc-200 bg-white p-2 text-sm dark:border-zinc-800 dark:bg-zinc-900"
            value={chartType}
            onChange={(e) => setChartType(e.target.value as ChartType)}
          >
            {chartTypes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-zinc-600 dark:text-zinc-300">
          X field
          <select
            className="mt-1 w-full rounded-md border border-zinc-200 bg-white p-2 text-sm dark:border-zinc-800 dark:bg-zinc-900"
            value={xField}
            onChange={(e) => setXField(e.target.value)}
          >
            {fields.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-zinc-600 dark:text-zinc-300">
          Y field
          <select
            className="mt-1 w-full rounded-md border border-zinc-200 bg-white p-2 text-sm dark:border-zinc-800 dark:bg-zinc-900"
            value={yField}
            onChange={(e) => setYField(e.target.value)}
          >
            {fields.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-zinc-600 dark:text-zinc-300 sm:col-span-2 lg:col-span-4">
          Color (optional)
          <select
            className="mt-1 w-full rounded-md border border-zinc-200 bg-white p-2 text-sm dark:border-zinc-800 dark:bg-zinc-900"
            value={colorField}
            onChange={(e) => setColorField(e.target.value)}
          >
            <option value="">None</option>
            {fields.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
      </div>
      {spec ? (
        <VegaLiteChart spec={spec} />
      ) : (
        <p className="text-sm text-zinc-500">Select fields to preview a chart.</p>
      )}
    </div>
  );
}
