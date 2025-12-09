import { RunConfig } from "@/lib/server/runs";
import { Download } from "lucide-react";

type Props = {
  runOptions: RunConfig[];
  runId?: string;
  selectedRun?: RunConfig;
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
};

export function RunControls({
  runOptions,
  runId,
  selectedRun,
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
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3 justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Run</span>
          <select
            className="bg-[var(--card)] border border-[var(--border)] rounded-md px-2 py-1 text-sm text-slate-100"
            value={runId || ""}
            onChange={(e) => onRunChange(e.target.value)}
            disabled={manifestLoading || refreshingRuns || !!manifestError || runOptions.length === 0}
          >
            {runOptions.length === 0 && <option value="">Loading runs…</option>}
            {runOptions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
        {selectedRun?.updated && <span className="text-xs text-slate-500">Updated {selectedRun.updated}</span>}
        <button
          className="text-xs text-slate-300 underline-offset-4 underline disabled:text-slate-500"
          onClick={onRefreshRuns}
          disabled={manifestLoading || refreshingRuns}
        >
          {refreshingRuns ? "Refreshing…" : "Refresh runs"}
        </button>
        <button
          className="text-xs text-slate-300 underline-offset-4 underline"
          onClick={onRefreshData}
          disabled={disableDataRefresh}
        >
          Refresh data
        </button>
        <a
          href={downloadHref}
          download
          className={`text-xs underline-offset-4 underline flex items-center gap-1 ${disableDownloadData ? "text-slate-500 cursor-not-allowed" : "text-slate-300 hover:text-white"}`}
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
        </a>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {refreshRunsError && <span className="text-xs text-red-300">Refresh failed: {refreshRunsError}</span>}
        {manifestError && <span className="text-xs text-red-300">Runs load failed; using default env run.</span>}
      </div>
    </div>
  );
}
