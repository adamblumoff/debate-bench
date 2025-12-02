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
        const yEncoding: Record<string, unknown> = { field: yField, type: yType };
        if (yType === "quantitative") {
          yEncoding.aggregate = "mean";
        }
        enc.y = yEncoding;
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
    <div className="grid gap-3 md:grid-cols-[300px_1fr]">
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
        <h4 className="text-sm font-semibold text-white">Chart builder</h4>
        <p className="text-xs text-slate-400 mb-3">Pick dataset and encodings</p>
        <div className="space-y-3 text-sm text-slate-200">
          <label className="flex flex-col gap-1">
            <span className="text-slate-400">Dataset</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
              value={datasetKey}
              onChange={(e) => setDatasetKey(e.target.value as DatasetKey)}
            >
              <option value="debates">Debates</option>
              <option value="judges">Judges</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-slate-400">Chart type</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
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
          <label className="flex flex-col gap-1">
            <span className="text-slate-400">X field</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
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
          <label className="flex flex-col gap-1">
            <span className="text-slate-400">Y field</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
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
          <label className="flex flex-col gap-1">
            <span className="text-slate-400">Color (optional)</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
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
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
        {spec ? (
          <VegaLiteChart spec={spec} />
        ) : (
          <p className="text-sm text-slate-400">Select fields to preview a chart.</p>
        )}
      </div>
    </div>
  );
}
