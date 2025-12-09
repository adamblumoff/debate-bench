"use client";

import { useEffect } from "react";
import Link from "next/link";
import { MIN_COMPARE, MAX_COMPARE } from "@/lib/compareLimits";
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

export function CompareDrawer({
  models,
  onRemove,
  derived,
  open,
  setOpen,
  lastAdded,
}: Props) {
  const hasAny = models.length > 0 && derived;
  const meetsMin = models.length >= MIN_COMPARE && derived;

  const rows =
    derived && hasAny
      ? models
          .map((m) => derived.modelStats.find((s) => s.model_id === m))
          .filter(Boolean)
          .slice(0, MAX_COMPARE)
      : [];

  const compareHref =
    models.length > 0
      ? `/builder?${models.map((m) => `compare=${encodeURIComponent(m)}`).join("&")}`
      : "/builder";

  useEffect(() => {
    if (lastAdded) setOpen(true);
  }, [lastAdded, setOpen]);

  return (
    <div
      className={`compare-drawer-left ${open && derived ? "open" : ""}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <div className="compare-tab">
        Compare {rows.length ? `(${rows.length})` : ""}
      </div>
      {derived && (
        <div className="compare-body">
          <div className="flex items-center justify-between mb-1 gap-2 min-w-0">
            <div className="min-w-0">
              <Link
                href={compareHref}
                aria-disabled={!meetsMin}
                tabIndex={!meetsMin ? -1 : 0}
                onClick={(e) => {
                  if (!meetsMin) e.preventDefault();
                }}
                className={`text-[12.5px] uppercase tracking-[0.18em] font-semibold underline-offset-4 transition-colors ${
                  meetsMin
                    ? "text-cyan-100 hover:text-white hover:underline"
                    : "text-slate-500 cursor-not-allowed"
                }`}
              >
                Compare
              </Link>
            </div>
            <div className="text-[10px] text-slate-400 text-right leading-tight min-w-0 overflow-wrap:anywhere">
              Pick 2–6 models
            </div>
          </div>
          {!meetsMin && (
            <p className="text-[10.5px] text-amber-200 mb-2">
              Add at least two models to open custom charts.
            </p>
          )}
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
                <p className="text-[12px] text-slate-300">
                  Elo {r!.rating.toFixed(0)} • Win {toPercent(r!.win_rate)}
                </p>
                <p className="text-[11px] text-slate-500">
                  Tokens {toTokens(r!.mean_prompt_tokens)} /{" "}
                  {toTokens(r!.mean_completion_tokens)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
