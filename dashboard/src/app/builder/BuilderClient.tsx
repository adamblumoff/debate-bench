"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { VisualizationSpec } from "vega-embed";
import { useCompareQuery } from "@/hooks/useCompareQuery";
import { MAX_COMPARE } from "@/lib/compareLimits";
import { buildChart } from "./actions";
import { VegaLiteChart } from "@/components/VegaLiteChart";

type DatasetKey = "debates" | "judges";
type ChartType = "bar" | "scatter" | "heatmap";

type Props = {
  allModels: string[];
  selectedModels: string[];
  fields: string[];
  fieldTypes: Record<string, "quantitative" | "nominal">;
  initialSpec: VisualizationSpec | null;
  initialRequest: {
    dataset: DatasetKey;
    chartType: ChartType;
    xField: string;
    yField?: string;
    colorField?: string;
  };
  runId?: string;
};

export default function BuilderClient({ allModels, selectedModels, fields, fieldTypes, initialSpec, initialRequest, runId }: Props) {
  const [dataset, setDataset] = useState<DatasetKey>(initialRequest.dataset);
  const [chartType, setChartType] = useState<ChartType>(initialRequest.chartType);
  const [xField, setXField] = useState<string>(initialRequest.xField);
  const [yField, setYField] = useState<string | undefined>(initialRequest.yField);
  const [colorField, setColorField] = useState<string | undefined>(initialRequest.colorField);
  const [availableFields, setAvailableFields] = useState<string[]>(fields);
  const [fieldTypesState, setFieldTypesState] = useState<Record<string, "quantitative" | "nominal">>(fieldTypes);
  const [spec, setSpec] = useState<VisualizationSpec | null>(initialSpec);

  const { selected, addModel, removeModel } = useCompareQuery(MAX_COMPARE);
  const [isPending, startTransition] = useTransition();
  const [search, setSearch] = useState("");
  const quantitativeFields = useMemo(
    () => availableFields.filter((f) => fieldTypesState[f] === "quantitative"),
    [availableFields, fieldTypesState]
  );
  const defaultHeatColor = quantitativeFields[0];

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
    let cf = hasColor ? next?.colorField : colorField;

    if (ct === "heatmap") {
      if (!cf || fieldTypesState[cf] !== "quantitative") {
        cf = defaultHeatColor;
      }
    } else {
      // Clear color when leaving heatmap unless explicitly set
      if (!hasColor) cf = undefined;
    }

    form.append("dataset", ds);
    form.append("chartType", ct);
    form.append("xField", xf);
    if (yf) form.append("yField", yf);
    if (cf) form.append("colorField", cf);
    if (runId) form.append("run", runId);
    selected.forEach((m) => form.append("models", m));

    startTransition(() => {
      buildChart(form).then((res) => {
        setSpec(res.spec);
        setAvailableFields(res.fields);
        if (res.fieldTypes) setFieldTypesState(res.fieldTypes);
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

  const resetFields = () => {
    setDataset(initialRequest.dataset);
    setChartType(initialRequest.chartType);
    setXField(initialRequest.xField);
    setYField(initialRequest.yField);
    setColorField(initialRequest.colorField);
    sendUpdate({
      dataset: initialRequest.dataset,
      chartType: initialRequest.chartType,
      xField: initialRequest.xField,
      yField: initialRequest.yField,
      colorField: initialRequest.colorField,
    });
  };

  const filteredModels = useMemo(() => {
    const term = search.toLowerCase().trim();
    const list = term ? allModels.filter((m) => m.toLowerCase().includes(term)) : allModels.slice();
    return list.sort((a, b) => {
      const aSel = selected.includes(a);
      const bSel = selected.includes(b);
      if (aSel === bSel) return a.localeCompare(b);
      return aSel ? -1 : 1;
    });
  }, [allModels, search, selected]);

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
    <div className="grid gap-4 md:grid-cols-[340px_1fr] items-start">
      <div className="card space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400 bg-[var(--card-alt)] px-2 py-1 rounded">Dataset</span>
            <select
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
              value={dataset}
              onChange={(e) => {
                const ds = e.target.value as DatasetKey;
                setDataset(ds);
                setYField(undefined);
                setColorField(undefined);
                sendUpdate({ dataset: ds, yField: undefined, colorField: undefined });
              }}
            >
              <option value="debates">Debates</option>
              <option value="judges">Judges</option>
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400 bg-[var(--card-alt)] px-2 py-1 rounded">Chart type</span>
            <select
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
              value={chartType}
              onChange={(e) => {
                const ct = e.target.value as ChartType;
                setChartType(ct);
                if (ct === "scatter" && !yField) {
                  const fallback = fieldOptions.find((f) => f !== xField) ?? fieldOptions[0] ?? "";
                  setYField(fallback || undefined);
                  sendUpdate({ chartType: ct, yField: fallback || undefined });
                } else if (ct === "heatmap") {
                  // Default axes for heatmap: X=con_model_id, Y=pro_model_id
                  const nextX = "con_model_id";
                  const nextY = "pro_model_id";
                  setXField(nextX);
                  setYField(nextY);
                  sendUpdate({ chartType: ct, xField: nextX, yField: nextY, colorField: colorField ?? defaultHeatColor });
                } else {
                  // force color default for heatmap, clear for others handled in sendUpdate
                  sendUpdate({ chartType: ct, colorField: undefined });
                }
             }}
            >
              <option value="bar">bar</option>
              <option value="scatter">scatter</option>
              <option value="heatmap">heatmap</option>
            </select>
          </label>
        </div>

        <div className="space-y-2">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400 bg-[var(--card-alt)] px-2 py-1 rounded">X field</span>
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
            <div className="flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400 bg-[var(--card-alt)] px-2 py-1 rounded">Y field</span>
              {chartType === "scatter" && (
                <span className="text-[10px] text-slate-400 border border-[var(--border)] rounded px-2 py-0.5">Required</span>
              )}
            </div>
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
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400 bg-[var(--card-alt)] px-2 py-1 rounded">Color {chartType === "heatmap" ? "(required)" : "(optional)"}</span>
            <select
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
              value={colorField ?? ""}
              onChange={(e) => {
                const v = e.target.value || undefined;
                setColorField(v);
                sendUpdate({ colorField: v });
              }}
            >
              {chartType !== "heatmap" && <option value="">None</option>}
              {quantitativeFields.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-center justify-between pt-1">
            <button
              type="button"
              className="text-xs text-slate-400 underline underline-offset-2"
              onClick={resetFields}
            >
              Reset fields
            </button>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
              Models ({selected.length}/6)
            </p>
            <span className="text-xs text-slate-400">
              Selected {selected.length} of {allModels.length}
            </span>
          </div>
          <div className="flex gap-2">
            <input
              type="search"
              placeholder="Search models"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
            />
            <button
              type="button"
              className="text-xs px-3 py-2 rounded-md border border-[var(--border)] text-slate-200"
              onClick={() => {
                const next = allModels.slice(0, 6);
                next.forEach((m) => addModel(m));
              }}
            >
              Select all
            </button>
            <button
              type="button"
              className="text-xs px-3 py-2 rounded-md border border-[var(--border)] text-slate-200"
              onClick={() => selected.forEach((m) => removeModel(m))}
            >
              Reset
            </button>
          </div>
          <div className="max-h-52 overflow-auto border border-[var(--border)] rounded-md p-2 space-y-1">
            {filteredModels.map((m) => {
              const checked = selected.includes(m);
              const disabled = !checked && selected.length >= 6;
              return (
                <label key={m} className="flex items-center gap-2 text-sm text-slate-200">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => {
                      if (checked) {
                        removeModel(m);
                      } else if (!disabled) {
                        addModel(m);
                      }
                    }}
                  />
                  <span className={checked ? "text-white" : ""}>{m}</span>
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
          {isPending && (
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="inline-block h-2 w-2 rounded-full bg-[var(--accent)] animate-pulse" />
              Updating…
            </div>
          )}
        </div>
        <div className="flex-1 relative">
          {isPending && <div className="absolute inset-0 bg-black/15 animate-pulse rounded-md z-10" />}
          {spec ? <VegaLiteChart spec={spec} /> : <p className="text-slate-400 text-sm">Select fields to render a chart.</p>}
        </div>
      </div>
    </div>
  );
}
