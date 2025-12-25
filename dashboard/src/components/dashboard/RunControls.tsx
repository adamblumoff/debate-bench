import Link from "next/link";
import { RunConfig } from "@/lib/server/runs";
import { Download } from "lucide-react";

type Props = {
  runOptions: RunConfig[];
  runId?: string;
  selectedRun?: RunConfig;
  modelCount?: number;
  debateCount?: number;
  manifestLoading: boolean;
  manifestError?: Error | null;
  refreshingRuns: boolean;
  refreshRunsError?: string | null;
  onRunChange: (id: string) => void;
  onRefreshRuns: () => void;
  onRefreshData: () => void;
  disableDataRefresh?: boolean;
  onDownloadData: () => void;
  disableDownloadData?: boolean;
  downloadHref: string;
  builderHref?: string;
  builderEnabled?: boolean;
};

export function RunControls({
  runOptions,
  runId,
  selectedRun,
  modelCount,
  debateCount,
  manifestLoading,
  manifestError,
  refreshingRuns,
  refreshRunsError,
  onRunChange,
  onRefreshRuns,
  onRefreshData,
  disableDataRefresh,
  onDownloadData,
  disableDownloadData,
  downloadHref,
  builderHref,
  builderEnabled,
}: Props) {
  const updatedLabel = selectedRun?.updated
    ? new Date(selectedRun.updated).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      })
    : null;

  return (
    <div className="space-y-1">
      <div className="run-toolbar">
        <div className="run-left">
          <span
            id="run-selector-label"
            className="text-[11px] uppercase tracking-[0.2em] text-slate-400"
          >
            Run
          </span>
          <select
            className="bg-[var(--card)] border border-[var(--border)] rounded-md px-2.5 py-2 text-sm text-slate-100"
            aria-labelledby="run-selector-label"
            value={runId || ""}
            onChange={(e) => onRunChange(e.target.value)}
            disabled={
              manifestLoading ||
              refreshingRuns ||
              !!manifestError ||
              runOptions.length === 0
            }
          >
            {runOptions.length === 0 && <option value="">Loading runs…</option>}
            {runOptions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
          <div className="run-meta-inline">
            {modelCount !== undefined && (
              <span className="run-chip">{modelCount} models</span>
            )}
            {debateCount !== undefined && (
              <span className="run-chip">{debateCount} debates</span>
            )}
            {updatedLabel && (
              <span className="run-chip">Updated {updatedLabel}</span>
            )}
          </div>
        </div>
        <div className="run-actions">
          {builderEnabled && builderHref && (
            <Link href={builderHref} className="btn-primary">
              Custom chart
            </Link>
          )}
          <button
            className="btn-ghost subtle disabled:opacity-60"
            onClick={onRefreshRuns}
            disabled={manifestLoading || refreshingRuns}
          >
            {refreshingRuns ? "Refreshing runs…" : "Refresh runs"}
          </button>
          <button
            className="btn-ghost subtle disabled:opacity-60"
            onClick={onRefreshData}
            disabled={disableDataRefresh}
          >
            Refresh data
          </button>
          <a
            href={downloadHref}
            download
            className={`btn-ghost subtle flex items-center gap-1 ${disableDownloadData ? "opacity-60 cursor-not-allowed" : "hover:border-[var(--accent)]"}`}
            onClick={(e) => {
              if (disableDownloadData) {
                e.preventDefault();
                return;
              }
              e.preventDefault();
              onDownloadData();
            }}
            aria-disabled={disableDownloadData}
            aria-label="Download debates JSONL"
            title="Download debates JSONL"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            <span>Download</span>
          </a>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {refreshRunsError && (
          <span className="text-xs text-red-300">
            Refresh failed: {refreshRunsError}
          </span>
        )}
        {manifestError && (
          <span className="text-xs text-red-300">
            Runs load failed; using default env run.
          </span>
        )}
      </div>
    </div>
  );
}
