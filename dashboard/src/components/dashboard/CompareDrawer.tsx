"use client";

import { useEffect } from "react";
import { DerivedData } from "@/lib/types";
import { toPercent, toTokens } from "@/lib/format";

type Props = {
  models: string[];
  onRemove: (id: string) => void;
  derived?: DerivedData;
  open: boolean;
  setOpen: (v: boolean) => void;
  lastAdded?: number;
};

export function CompareDrawer({ models, onRemove, derived, open, setOpen, lastAdded }: Props) {
  const hasData = models.length > 0 && derived;

  const rows =
    hasData && derived
      ? models
          .map((m) => derived.modelStats.find((s) => s.model_id === m))
          .filter(Boolean)
          .slice(0, 6)
      : [];

  useEffect(() => {
    if (lastAdded) setOpen(true);
  }, [lastAdded, setOpen]);

  return (
    <div
      className={`compare-drawer-left ${open && hasData ? "open" : ""}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <div className="compare-tab">Compare {rows.length ? `(${rows.length})` : ""}</div>
      {hasData && (
        <div className="compare-body">
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Compare</p>
              <h3 className="text-lg font-semibold text-white">Pinned models ({rows.length})</h3>
            </div>
            <div className="text-xs text-slate-400">Shareable via URL params</div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {rows.map((r) => (
              <div key={r!.model_id} className="compare-card">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-white truncate">{r!.model_id}</p>
                  <button className="text-xs text-slate-400 hover:text-red-300" onClick={() => onRemove(r!.model_id)}>
                    remove
                  </button>
                </div>
                <p className="text-sm text-slate-300">Elo {r!.rating.toFixed(0)} • Win {toPercent(r!.win_rate)}</p>
                <p className="text-xs text-slate-500">
                  Tokens {toTokens(r!.mean_prompt_tokens)} / {toTokens(r!.mean_completion_tokens)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
