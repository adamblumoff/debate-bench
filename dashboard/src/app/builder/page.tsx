"use server";

import { Suspense } from "react";
import { VisualizationSpec } from "vega-embed";
import { getMetrics } from "@/lib/server/metrics";
import { buildChartSpec, buildFields, ChartRequest, DatasetKey, DataRow } from "@/lib/server/chartSpec";
import { DerivedData } from "@/lib/types";
import BuilderClient from "./BuilderClient";

export const dynamic = "force-dynamic";

type BuilderPageProps = {
  searchParams: { [key: string]: string | string[] | undefined };
};

function parseCompare(params: BuilderPageProps["searchParams"]): string[] {
  const raw = params.compare;
  if (!raw) return [];
  if (Array.isArray(raw)) return raw.flatMap((v) => v.split(",")).filter(Boolean);
  return raw.split(",").filter(Boolean);
}

function chooseModels(derived: DerivedData, requested: string[]): string[] {
  const valid = requested.filter((m) => derived.models.includes(m));
  if (valid.length) return Array.from(new Set(valid));
  // Default: top 6 by Elo
  return derived.modelStats.slice(0, 6).map((m) => m.model_id);
}

function filterRows(derived: DerivedData, models: string[], dataset: DatasetKey): DataRow[] {
  const set = new Set(models);
  if (dataset === "debates") {
    return derived.debateRows.filter(
      (r) => set.has(r.pro_model_id as string) && set.has(r.con_model_id as string)
    );
  }
  return derived.judgeRows.filter(
    (r) => set.has(r.pro_model_id as string) && set.has(r.con_model_id as string)
  );
}

export default async function BuilderPage({ searchParams }: BuilderPageProps) {
  const metrics = await getMetrics(false);
  const derived = metrics.derived;
  const requested = parseCompare(searchParams);
  const selectedModels = chooseModels(derived, requested);

  const dataset: DatasetKey = "debates";
  const rows = filterRows(derived, selectedModels, dataset);
  const fields = buildFields(derived, dataset);

  const initialRequest: ChartRequest = {
    dataset,
    chartType: "bar",
    xField: "pro_model_id",
    yField: undefined,
    colorField: "",
  };

  const initialSpec: VisualizationSpec | null = buildChartSpec(rows, initialRequest);

  return (
    <Suspense fallback={<div className="container-page text-slate-400">Loading builder…</div>}>
      <div className="container-page space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Custom charts</p>
            <h1 className="text-3xl font-semibold text-white">Model comparisons your way</h1>
            <p className="text-slate-400 text-sm">
              Preloaded with your current compares ({selectedModels.length} models). Adjust fields and chart type; data and specs are built on the server.
            </p>
          </div>
        </div>
        <BuilderClient
          allModels={derived.models}
          selectedModels={selectedModels}
          fields={fields}
          initialSpec={initialSpec}
          initialRequest={initialRequest}
        />
      </div>
    </Suspense>
  );
}
