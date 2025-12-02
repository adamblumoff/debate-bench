"use client";

import { DerivedData } from "@/lib/types";
import { toPercent, toTokens } from "@/lib/format";

export function CompareDrawer({ models, onRemove, derived }: { models: string[]; onRemove: (id: string) => void; derived?: DerivedData }) {
  if (!models.length || !derived) return null;
  const rows = models
    .map((m) => derived.modelStats.find((s) => s.model_id === m))
    .filter(Boolean)
    .slice(0, 4);
  return (
    <div className="compare-drawer">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Compare</p>
          <h3 className="text-lg font-semibold text-white">Pinned models ({rows.length})</h3>
        </div>
        <div className="text-xs text-slate-400">Shareable via URL params</div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
        {rows.map((r) => (
          <div key={r!.model_id} className="compare-card">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-white">{r!.model_id}</p>
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
  );
}
