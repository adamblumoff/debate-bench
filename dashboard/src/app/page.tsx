"use client";

import { Suspense, useMemo, useCallback, useState, useEffect } from "react";
import useSWR from "swr";
import { useRouter, useSearchParams } from "next/navigation";
import { useEnsureData } from "@/store/useDataStore";
import { useHighlightsState } from "@/hooks/useHighlightsState";
import { useCompareQuery } from "@/hooks/useCompareQuery";
import { usePricingData } from "@/hooks/usePricingData";
import { Hero } from "@/components/dashboard/Hero";
import { FilterBar } from "@/components/dashboard/FilterBar";
import { CompareDrawer } from "@/components/dashboard/CompareDrawer";
import { PricingTable } from "@/components/dashboard/PricingTable";
import { RunControls } from "@/components/dashboard/RunControls";
import { KpiStrip } from "@/components/dashboard/KpiStrip";
import { HighlightsSection } from "@/components/dashboard/HighlightsSection";
import {
  buildHighlightLists,
  buildHighlightSpecs,
  buildKpis,
  selectHighlightDerived,
} from "@/lib/highlights";
import { ENABLE_BUILDER, ENABLE_COMPARE } from "@/lib/featureFlags";
import { ChartCard } from "@/components/ChartCard";
import { VegaLiteChart } from "@/components/VegaLiteChart";
import { LoadState } from "@/components/LoadState";
import { ManifestResponse } from "@/lib/apiTypes";

const fetcher = (url: string) =>
  fetch(url).then((res) => {
    if (!res.ok) throw new Error(`Fetch failed ${res.status}`);
    return res.json();
  });

function buildDownloadHref(runId?: string) {
  const params = new URLSearchParams();
  if (runId) params.set("run", runId);
  const qs = params.toString();
  return qs ? `/api/debates?${qs}` : "/api/debates";
}

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    data: manifest,
    isLoading: manifestLoading,
    error: manifestError,
    mutate: refreshManifest,
  } = useSWR<ManifestResponse>("/api/manifest", fetcher, {
    revalidateOnFocus: false,
  });

  const runFromUrl = searchParams.get("run") || undefined;
  const builderHref = useMemo(() => {
    if (!ENABLE_BUILDER) return null;
    const params = new URLSearchParams();
    searchParams.getAll("compare").forEach((v) => params.append("compare", v));
    const run = searchParams.get("run");
    if (run) params.set("run", run);
    const qs = params.toString();
    return qs ? `/builder?${qs}` : "/builder";
  }, [searchParams]);
  const runId = useMemo(() => {
    if (!manifest) return runFromUrl;
    if (runFromUrl && manifest.runs.some((r) => r.id === runFromUrl))
      return runFromUrl;
    return manifest.defaultRunId;
  }, [manifest, runFromUrl]);

  const runReady = Boolean(runId);

  useEffect(() => {
    if (!manifest || !runId || runId === runFromUrl) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("run", runId);
    router.replace(`/?${params.toString()}`, { scroll: false });
  }, [manifest, runId, runFromUrl, router, searchParams]);

  const { status, error, derived, derivedByCategory, meta, load } =
    useEnsureData(runId, runReady);
  const { activeTab, setActiveTab, category, setCategory } =
    useHighlightsState();
  const {
    selected: compareModels,
    addModel: addCompareModel,
    removeModel,
  } = useCompareQuery(undefined, ENABLE_COMPARE);
  // Only apply category filter to highlights/category heatmap; keep full derived for global metrics.
  const highlightDerived = useMemo(
    () => selectHighlightDerived(derived, derivedByCategory, category),
    [derived, derivedByCategory, category],
  );

  const modelIds = derived?.modelStats.map((m) => m.model_id) || [];
  const pricing = usePricingData(modelIds, runId);
  const [compareOpen, setCompareOpen] = useState(false);
  const [lastAdded, setLastAdded] = useState<number>();
  const [refreshingRuns, setRefreshingRuns] = useState(false);
  const [refreshRunsError, setRefreshRunsError] = useState<string | null>(null);

  const addModel = useCallback(
    (id: string) => {
      addCompareModel(id);
      setCompareOpen(true);
      setLastAdded(Date.now());
    },
    [addCompareModel],
  );

  const categories = useMemo(() => meta?.categories || [], [meta]);
  const topN = useMemo(() => {
    const count = derived?.modelStats.length ?? meta?.modelCount;
    if (typeof count === "number" && count > 0) return count;
    return 6;
  }, [derived?.modelStats.length, meta?.modelCount]);
  const resetFilters = useCallback(() => {
    setCategory("all");
  }, [setCategory]);

  const sortedRunOptions = useMemo(() => {
    const options = manifest?.runs || [];
    return [...options].sort((a, b) => {
      const ta = a.updated ? Date.parse(a.updated) : 0;
      const tb = b.updated ? Date.parse(b.updated) : 0;
      if (tb !== ta) return tb - ta;
      return a.label.localeCompare(b.label);
    });
  }, [manifest?.runs]);
  const selectedRun =
    sortedRunOptions.find((r) => r.id === runId) ||
    (manifest && sortedRunOptions.find((r) => r.id === manifest.defaultRunId));

  const onRunChange = useCallback(
    (id: string) => {
      if (!id) return;
      const params = new URLSearchParams(searchParams.toString());
      params.set("run", id);
      router.replace(`/?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const onRefreshRuns = useCallback(() => {
    setRefreshingRuns(true);
    setRefreshRunsError(null);
    refreshManifest(fetcher("/api/manifest?refresh=1"), { revalidate: false })
      .catch((err) => setRefreshRunsError(err?.message || "Refresh failed"))
      .finally(() => setRefreshingRuns(false));
  }, [refreshManifest]);

  const onRefreshData = useCallback(() => {
    load(runId, true);
  }, [load, runId]);
  const onDownloadData = useCallback(() => {
    const link = document.createElement("a");
    link.href = buildDownloadHref(runId);
    link.download = "";
    document.body.appendChild(link);
    link.click();
    link.remove();
  }, [runId]);

  const downloadHref = useMemo(() => buildDownloadHref(runId), [runId]);

  const specs = useMemo(
    () => buildHighlightSpecs(highlightDerived, derived, topN, category),
    [highlightDerived, derived, topN, category],
  );
  const highlightData = useMemo(
    () => buildHighlightLists(highlightDerived, pricing, topN),
    [highlightDerived, pricing, topN],
  );
  const kpi = useMemo(() => buildKpis(derived), [derived]);

  return (
    <main className="min-h-screen text-slate-50 bg-[var(--bg-base)]">
      <div className="container-page space-y-8 pb-28">
        <div className="flex flex-col gap-3">
          <Hero />
        </div>

        <FilterBar
          categories={categories}
          category={category}
          onCategory={setCategory}
          onResetFilters={resetFilters}
        />

        <div className="flex flex-col gap-3">
          <RunControls
            runOptions={sortedRunOptions}
            runId={runId}
            selectedRun={selectedRun}
            modelCount={derived?.models.length ?? meta?.modelCount}
            debateCount={meta?.debateCount}
            manifestLoading={manifestLoading}
            manifestError={manifestError}
            refreshingRuns={refreshingRuns}
            refreshRunsError={refreshRunsError}
            onRunChange={onRunChange}
            onRefreshRuns={onRefreshRuns}
            onRefreshData={onRefreshData}
            onDownloadData={onDownloadData}
            disableDataRefresh={status === "loading"}
            disableDownloadData={status === "loading"}
            downloadHref={downloadHref}
            builderHref={builderHref || undefined}
            builderEnabled={ENABLE_BUILDER}
          />
        </div>

        <HighlightsSection
          status={status}
          error={error}
          derived={derived}
          specs={specs}
          highlightData={highlightData}
          activeTab={activeTab}
          onTab={setActiveTab}
          onAddModel={ENABLE_COMPARE ? addModel : undefined}
          pricing={pricing}
          topN={topN}
          modelCount={meta?.modelCount}
          onResetFilters={resetFilters}
        />

        {status === "ready" && derived ? (
          <div className="space-y-6">
            <KpiStrip kpi={kpi} />

            {/* Models section removed (Elo + win rate duplicated in highlights) */}

            <section
              id="topics"
              className="grid gap-4 md:grid-cols-12 items-stretch"
            >
              <div className="md:col-span-6 min-w-0">
                <ChartCard
                  title="Head-to-head win rate"
                  subtitle="Row model vs column model"
                  className="chart-card h-full"
                >
                  {specs.h2h && <VegaLiteChart spec={specs.h2h} />}
                </ChartCard>
              </div>
              <div className="md:col-span-6 min-w-0">
                <ChartCard
                  title="Topic/category win rates"
                  subtitle="Per model × category heatmap"
                  className="chart-card h-full"
                >
                  {specs.categoryHeat && (
                    <VegaLiteChart spec={specs.categoryHeat} />
                  )}
                </ChartCard>
              </div>
            </section>

            <section id="judges" className="grid gap-4 md:grid-cols-12">
              <div className="md:col-span-6 min-w-0">
                <ChartCard
                  title="Judge agreement"
                  className="chart-card h-full overflow-hidden"
                >
                  {specs.judgeHeat && <VegaLiteChart spec={specs.judgeHeat} />}
                </ChartCard>
              </div>
              <div className="md:col-span-6 min-w-0">
                <ChartCard
                  title="Side bias (pro minus con win rate)"
                  className="chart-card h-full overflow-hidden"
                >
                  {specs.sideBias && <VegaLiteChart spec={specs.sideBias} />}
                </ChartCard>
              </div>
              <div className="md:col-span-12 min-w-0">
                <ChartCard
                  title="Judge side preference (CV mean)"
                  subtitle="5-fold CV mean of adjusted bias; topic×model interactions included."
                  className="chart-card h-full overflow-hidden"
                >
                  {specs.judgeSideBiasCv && (
                    <VegaLiteChart spec={specs.judgeSideBiasCv} />
                  )}
                </ChartCard>
              </div>
            </section>

            <section id="pricing" className="space-y-3">
              <PricingTable
                pricing={pricing}
                onAdd={ENABLE_COMPARE ? addModel : undefined}
              />
            </section>
          </div>
        ) : (
          <div className="card text-slate-200">
            <LoadState status={status} error={error} />
            {status === "idle" && (
              <p className="text-sm text-slate-400">
                Initializing data loader…
              </p>
            )}
            {status === "loading" && <div className="mt-3 h-32 skeleton" />}
          </div>
        )}
      </div>

      {ENABLE_COMPARE && (
        <CompareDrawer
          models={compareModels}
          onRemove={removeModel}
          derived={derived}
          open={compareOpen}
          setOpen={setCompareOpen}
          lastAdded={lastAdded}
          builderEnabled={ENABLE_BUILDER}
        />
      )}
    </main>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="container-page text-slate-400">Loading dashboard…</div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
