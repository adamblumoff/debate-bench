"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { VisualizationSpec } from "vega-embed";
import { useCompareQuery } from "@/hooks/useCompareQuery";
import { buildChart } from "./actions";
import { VegaLiteChart } from "@/components/VegaLiteChart";

type DatasetKey = "debates" | "judges";
type ChartType = "bar" | "scatter" | "heatmap" | "boxplot";

type Props = {
  allModels: string[];
  selectedModels: string[];
  fields: string[];
  initialSpec: VisualizationSpec | null;
  initialRequest: {
    dataset: DatasetKey;
    chartType: ChartType;
    xField: string;
    yField?: string;
    colorField?: string;
  };
};

export default function BuilderClient({ allModels, selectedModels, fields, initialSpec, initialRequest }: Props) {
  const [dataset, setDataset] = useState<DatasetKey>(initialRequest.dataset);
  const [chartType, setChartType] = useState<ChartType>(initialRequest.chartType);
  const [xField, setXField] = useState<string>(initialRequest.xField);
  const [yField, setYField] = useState<string | undefined>(initialRequest.yField);
  const [colorField, setColorField] = useState<string | undefined>(initialRequest.colorField);
  const [availableFields, setAvailableFields] = useState<string[]>(fields);
  const [spec, setSpec] = useState<VisualizationSpec | null>(initialSpec);

  const { selected, addModel, removeModel } = useCompareQuery(6);
  const [isPending, startTransition] = useTransition();

  // Seed compare selection from server defaults if query is empty.
  useEffect(() => {
    if (!selected.length && selectedModels.length) {
      selectedModels.forEach((m) => addModel(m));
    }
  }, [selected.length, selectedModels, addModel]);

  // Prevent empty selection by re-adding the first default.
  useEffect(() => {
    if (selected.length === 0 && allModels.length) {
      addModel(selectedModels[0] || allModels[0]);
    }
  }, [selected.length, allModels, addModel, selectedModels]);

  const sendUpdate = (
    next?: Partial<{ dataset: DatasetKey; chartType: ChartType; xField: string; yField?: string; colorField?: string }>
  ) => {
    const form = new FormData();
    const ds = next?.dataset ?? dataset;
    const ct = next?.chartType ?? chartType;
    const xf = next?.xField ?? xField;
    const hasY = next && Object.prototype.hasOwnProperty.call(next, "yField");
    const hasColor = next && Object.prototype.hasOwnProperty.call(next, "colorField");
    const yf = hasY ? next?.yField : yField;
    const cf = hasColor ? next?.colorField : colorField;

    form.append("dataset", ds);
    form.append("chartType", ct);
    form.append("xField", xf);
    if (yf) form.append("yField", yf);
    if (cf) form.append("colorField", cf);
    selected.forEach((m) => form.append("models", m));

    startTransition(() => {
      buildChart(form).then((res) => {
        setSpec(res.spec);
        setAvailableFields(res.fields);
      });
    });
  };

  // Trigger refresh when selection changes.
  useEffect(() => {
    if (selected.length) sendUpdate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected.join("|")]);

  const fieldOptions = useMemo(() => availableFields, [availableFields]);

  useEffect(() => {
    if (availableFields.length === 0) return;
    if (!availableFields.includes(xField)) {
      const next = availableFields[0];
      setXField(next);
      sendUpdate({ xField: next });
    }
    if (yField && !availableFields.includes(yField)) {
      setYField(undefined);
      sendUpdate({ yField: undefined });
    }
    if (colorField && !availableFields.includes(colorField)) {
      setColorField(undefined);
      sendUpdate({ colorField: undefined });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableFields.join("|")]);

  return (
    <div className="grid gap-4 md:grid-cols-[320px_1fr]">
      <div className="card space-y-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Dataset</p>
          <select
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
            value={dataset}
            onChange={(e) => {
              const ds = e.target.value as DatasetKey;
              setDataset(ds);
              // reset y/color for safety
              setYField(undefined);
              setColorField(undefined);
              sendUpdate({ dataset: ds, yField: undefined, colorField: undefined });
            }}
          >
            <option value="debates">Debates</option>
            <option value="judges">Judges</option>
          </select>
        </div>

        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Chart type</p>
          <select
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
            value={chartType}
            onChange={(e) => {
              const ct = e.target.value as ChartType;
              setChartType(ct);
              // Ensure y is set for types that need it
              if ((ct === "scatter" || ct === "boxplot") && !yField) {
                const fallback = fieldOptions.find((f) => f !== xField) ?? fieldOptions[0] ?? "";
                setYField(fallback || undefined);
                sendUpdate({ chartType: ct, yField: fallback || undefined });
              } else {
                sendUpdate({ chartType: ct });
              }
            }}
          >
            <option value="bar">bar</option>
            <option value="scatter">scatter</option>
            <option value="heatmap">heatmap</option>
            <option value="boxplot">boxplot</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs">X field</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
              value={xField}
              onChange={(e) => {
                const v = e.target.value;
                setXField(v);
                sendUpdate({ xField: v });
              }}
            >
              {fieldOptions.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs">Y field (blank = count)</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
              value={yField ?? ""}
              onChange={(e) => {
                const v = e.target.value || undefined;
                setYField(v);
                sendUpdate({ yField: v });
              }}
            >
              <option value="">(count)</option>
              {fieldOptions.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs">Color (optional)</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
              value={colorField ?? ""}
              onChange={(e) => {
                const v = e.target.value || undefined;
                setColorField(v);
                sendUpdate({ colorField: v });
              }}
            >
              <option value="">None</option>
              {fieldOptions.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Models ({selected.length}/6)</p>
          <div className="max-h-48 overflow-auto border border-[var(--border)] rounded-md p-2 space-y-1">
            {allModels.map((m) => {
              const checked = selected.includes(m);
              return (
                <label key={m} className="flex items-center gap-2 text-sm text-slate-200">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      if (checked) {
                        removeModel(m);
                      } else {
                        addModel(m);
                      }
                    }}
                  />
                  <span>{m}</span>
                </label>
              );
            })}
          </div>
        </div>
      </div>

      <div className="card min-h-[420px] flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Preview</p>
            <p className="text-slate-300 text-sm">Data and spec are composed on the server.</p>
          </div>
          {isPending && <span className="text-xs text-slate-400">Updating…</span>}
        </div>
        <div className="flex-1">
          {spec ? <VegaLiteChart spec={spec} /> : <p className="text-slate-400 text-sm">Select fields to render a chart.</p>}
        </div>
      </div>
    </div>
  );
}
