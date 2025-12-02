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
          <div className="flex items-center justify-between mb-1 gap-2 min-w-0">
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Compare</p>
            </div>
            <div className="text-[10px] text-slate-400 text-right leading-tight min-w-0 overflow-wrap:anywhere">
              Max 4 models
            </div>
          </div>
          <div className="grid gap-2">
            {rows.map((r) => (
              <div key={r!.model_id} className="compare-card">
                <div className="flex items-center justify-between">
                  <p className="text-[12.5px] font-semibold text-white leading-tight overflow-wrap:anywhere min-w-0">
                    {r!.model_id}
                  </p>
                  <button
                    className="text-[10px] text-slate-400 hover:text-red-300 flex-shrink-0"
                    onClick={() => onRemove(r!.model_id)}
                  >
                    remove
                  </button>
                </div>
                <p className="text-[12px] text-slate-300">Elo {r!.rating.toFixed(0)} • Win {toPercent(r!.win_rate)}</p>
                <p className="text-[11px] text-slate-500">
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
