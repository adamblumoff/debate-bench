"use client";

import { useRef } from "react";
import Link from "next/link";
import { MIN_COMPARE, MAX_COMPARE } from "@/lib/compareLimits";
import { DerivedData } from "@/lib/types";
import { toPercent, toTokens } from "@/lib/format";
import posthog from "posthog-js";
import { cn } from "@/lib/cn";

type Props = {
  models: string[];
  onRemove: (id: string) => void;
  derived?: DerivedData;
  open: boolean;
  setOpen: (v: boolean) => void;
  lastAdded?: number;
  builderEnabled?: boolean;
};

export function CompareDrawer({
  models,
  onRemove,
  derived,
  open,
  setOpen,
  lastAdded,
  builderEnabled = false,
}: Props) {
  const hasAny = models.length > 0;
  const meetsMin = models.length >= MIN_COMPARE;

  const rows =
    derived && hasAny
      ? models
          .map((m) => derived.modelStats.find((s) => s.model_id === m))
          .filter(Boolean)
          .slice(0, MAX_COMPARE)
      : [];

  // Track if drawer was previously open to avoid duplicate events
  const wasOpenRef = useRef(open);

  const openDrawer = () => {
    if (!wasOpenRef.current) {
      posthog.capture("compare_drawer_opened", {
        models_count: models.length,
      });
    }
    wasOpenRef.current = true;
    setOpen(true);
  };

  const closeDrawer = () => {
    wasOpenRef.current = false;
    setOpen(false);
  };

  // Suppress unused lastAdded warning - prop is kept for backward compatibility
  // The parent component now controls drawer opening directly via setOpen
  void lastAdded;

  return (
    <div
      className={cn("compare-drawer-left", open && "open")}
      onMouseEnter={openDrawer}
      onMouseLeave={closeDrawer}
    >
      <button
        type="button"
        className="compare-tab"
        onClick={() => (open ? closeDrawer() : openDrawer())}
        aria-label="Toggle compare drawer"
      >
        Compare {rows.length ? `(${rows.length})` : ""}
      </button>
      <div className="compare-body">
        <div className="flex items-center justify-between mb-1 gap-2 min-w-0">
          <div className="min-w-0">
            {builderEnabled ? (
              <Link
                href={
                  models.length > 0
                    ? `/builder?${models.map((m) => `compare=${encodeURIComponent(m)}`).join("&")}`
                    : "/builder"
                }
                aria-disabled={!meetsMin}
                tabIndex={!meetsMin ? -1 : 0}
                onClick={(e) => {
                  if (!meetsMin) e.preventDefault();
                }}
                className={cn(
                  "text-[12.5px] uppercase font-semibold underline-offset-4 transition-colors",
                  meetsMin
                    ? "text-[var(--accent-strong)] hover:text-[var(--text-primary)] hover:underline"
                    : "text-[#585888] cursor-not-allowed",
                )}
              >
                Compare
              </Link>
            ) : (
              <span className="text-[12.5px] uppercase font-semibold text-[#585888]">
                Custom charts off
              </span>
            )}
          </div>
          <div className="text-[10px] text-[var(--text-muted)] text-right leading-tight min-w-0 overflow-wrap:anywhere">
            {builderEnabled ? "Pick 2–6 models" : "Selection saved locally"}
          </div>
        </div>
        {builderEnabled ? (
          !meetsMin && (
            <p className="text-[10.5px] text-[var(--accent-warn)] mb-2">
              Add at least two models to open custom charts.
            </p>
          )
        ) : (
          <p className="text-[10.5px] text-[#585888] mb-2">
            Custom chart builder is hidden for now.
          </p>
        )}
        <div className="grid gap-2">
          {rows.length ? (
            rows.map((r) => (
              <div key={r!.model_id} className="compare-card">
                <div className="flex items-center justify-between">
                  <p className="text-[12.5px] font-semibold text-[var(--text-primary)] leading-tight overflow-wrap:anywhere min-w-0">
                    {r!.model_id}
                  </p>
                  <button
                    className="text-[10px] text-[var(--text-muted)] hover:text-[var(--accent-strong)] flex-shrink-0"
                    onClick={() => onRemove(r!.model_id)}
                    aria-label={`Remove ${r!.model_id} from comparison`}
                  >
                    remove
                  </button>
                </div>
                <p className="text-[12px] text-[var(--text-muted)] tabular-nums">
                  Elo {r!.rating.toFixed(0)} • Win {toPercent(r!.win_rate)}
                </p>
                <p className="text-[11px] text-[#585888] tabular-nums">
                  Tokens {toTokens(r!.mean_prompt_tokens)} /{" "}
                  {toTokens(r!.mean_completion_tokens)}
                </p>
              </div>
            ))
          ) : (
            <p className="text-[11px] text-[#585888]">
              {models.length
                ? "Loading compare stats…"
                : "Pick models to start comparing."}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
