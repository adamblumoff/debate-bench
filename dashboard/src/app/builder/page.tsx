import { Suspense } from "react";
import { VisualizationSpec } from "vega-embed";
import { getMetrics } from "@/lib/server/metrics";
import {
  buildChartSpec,
  buildFields,
  buildFieldTypes,
  ChartRequest,
  DatasetKey,
} from "@/lib/server/chartSpec";
import { parseCompareParam, chooseModels, filterRowsByModels } from "./shared";
import BuilderClient from "./BuilderClient";
import Link from "next/link";

export const dynamic = "force-dynamic";

type BuilderPageProps = {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function BuilderPage({ searchParams }: BuilderPageProps) {
  const resolvedParams = await searchParams;
  const runId =
    typeof resolvedParams.run === "string" ? resolvedParams.run : undefined;
  const metrics = await getMetrics(false, runId, undefined, {
    includeRows: true,
  });
  const derived = metrics.derived;
  const requested = parseCompareParam(resolvedParams.compare);
  const selectedModels = chooseModels(derived, requested);

  const dataset: DatasetKey = "debates";
  const rows = filterRowsByModels(derived, selectedModels, dataset);
  const fields = buildFields(derived, dataset);
  const fieldTypes = buildFieldTypes(rows);

  const initialRequest: ChartRequest = {
    dataset,
    chartType: "bar",
    xField: "pro_model_id",
    yField: undefined,
    colorField: undefined,
  };

  const initialSpec: VisualizationSpec | null = buildChartSpec(
    rows,
    initialRequest,
  );

  return (
    <Suspense
      fallback={
        <div className="container-page text-slate-400">Loading builder…</div>
      }
    >
      <div className="container-page space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
              Custom charts
            </p>
            <h1 className="text-3xl font-semibold text-white">
              Model comparisons your way
            </h1>
            <p className="text-slate-400 text-sm">
              Preloaded with your current compares ({selectedModels.length}{" "}
              models). Adjust fields and chart type; data and specs are built on
              the server.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="btn-ghost px-4 py-2 border border-[var(--border)] rounded-md text-sm text-slate-200"
            >
              ← Back to dashboard
            </Link>
          </div>
        </div>
        <BuilderClient
          allModels={derived.models}
          selectedModels={selectedModels}
          fields={fields}
          fieldTypes={fieldTypes}
          initialSpec={initialSpec}
          initialRequest={initialRequest}
          runId={runId}
        />
      </div>
    </Suspense>
  );
}
