import { Suspense } from "react";
import { VisualizationSpec } from "vega-embed";
import { getMetrics } from "@/lib/server/metrics";
import { buildChartSpec, buildFields, ChartRequest, DatasetKey } from "@/lib/server/chartSpec";
import { parseCompareParam, chooseModels, filterRowsByModels } from "./shared";
import BuilderClient from "./BuilderClient";

export const dynamic = "force-dynamic";

type BuilderPageProps = {
  searchParams: { [key: string]: string | string[] | undefined };
};

export default async function BuilderPage({ searchParams }: BuilderPageProps) {
  const metrics = await getMetrics(false);
  const derived = metrics.derived;
  const requested = parseCompareParam(searchParams.compare);
  const selectedModels = chooseModels(derived, requested);

  const dataset: DatasetKey = "debates";
  const rows = filterRowsByModels(derived, selectedModels, dataset);
  const fields = buildFields(derived, dataset);

  const initialRequest: ChartRequest = {
    dataset,
    chartType: "bar",
    xField: "pro_model_id",
    yField: undefined,
    colorField: undefined,
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
