"use client";

import { toTokens } from "@/lib/format";
import posthog from "posthog-js";
import { cn } from "@/lib/cn";

function formatModelId(id: string) {
  if (id.includes("/")) return id;
  const firstDash = id.indexOf("-");
  if (firstDash <= 0) return id;
  const provider = id.slice(0, firstDash);
  const rest = id.slice(firstDash + 1);
  if (!rest) return id;
  return `${provider}/${rest}`;
}

export function MiniBarList({
  title,
  items,
  formatter,
  onAdd,
  expected,
  className = "",
}: {
  title: string;
  items: { label: string; value: number; hint?: string }[];
  formatter: (n: number) => string;
  onAdd?: (id: string) => void;
  expected?: number;
  className?: string;
}) {
  const desired = expected !== undefined ? expected : items.length;
  const rowHeight = 56;
  const minHeight = desired ? desired * rowHeight : undefined;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className={cn("card flex-1 highlight-card", className)}>
      <header className="flex items-center justify-between mb-2">
        <p className="text-sm text-[var(--text-muted)]">{title}</p>
        <div className="chart-legend-bar" />
      </header>
      <div className="space-y-2" style={minHeight ? { minHeight } : undefined}>
        {items.map((i) => (
          <div key={i.label} className="flex items-center gap-3 min-w-0">
            <div className="w-full min-w-0">
              <div className="flex justify-between gap-2 text-xs text-[var(--text-muted)] min-w-0">
                <span className="min-w-0 flex-1 truncate" title={i.label}>
                  {formatModelId(i.label)}
                </span>
                <span className="shrink-0 text-[#c0c0c0]">
                  {formatter(i.value)}
                </span>
              </div>
              <div className="h-2.5 rounded-none bg-[#1a1a1a] overflow-hidden">
                <div
                  className="h-full rounded-none bg-[var(--accent)]"
                  style={{ width: `${Math.max((i.value / max) * 100, 4)}%` }}
                />
              </div>
              {i.hint && (
                <p className="text-[11px] text-[#4a4a4a] mt-0.5">{i.hint}</p>
              )}
            </div>
            {onAdd && (
              <button
                className="text-xs px-2 py-1 rounded-none border border-[var(--border)] hover:border-[var(--accent)] text-[#c0c0c0]"
                onClick={() => onAdd(i.label)}
              >
                + Compare
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function TokenBarList({
  title,
  items,
  onAdd,
  className = "",
}: {
  title: string;
  items: { label: string; prompt: number; output: number }[];
  onAdd?: (id: string) => void;
  className?: string;
}) {
  const max = Math.max(...items.map((i) => i.prompt + i.output), 1);
  return (
    <div className={cn("card flex-1 highlight-card", className)}>
      <header className="flex items-center justify-between mb-2">
        <p className="text-sm text-[var(--text-muted)]">{title}</p>
        <div className="chart-legend-bar" />
      </header>
      <div className="space-y-2">
        {items.map((i) => {
          const total = i.prompt + i.output;
          const promptPct = total ? (i.prompt / total) * 100 : 50;
          return (
            <div key={i.label} className="flex items-center gap-3 min-w-0">
              <div className="w-full min-w-0">
                <div className="flex justify-between gap-2 text-xs text-[var(--text-muted)] min-w-0">
                  <span className="min-w-0 flex-1 truncate" title={i.label}>
                    {formatModelId(i.label)}
                  </span>
                  <span className="shrink-0 text-[#c0c0c0]">
                    {toTokens(total)}
                  </span>
                </div>
                <div className="h-2.5 rounded-none bg-[#1a1a1a] overflow-hidden flex">
                  <div
                    className="h-full bg-[var(--accent)]"
                    style={{ width: `${(total / max) * 100}%` }}
                  >
                    <div
                      className="h-full bg-[var(--accent)]"
                      style={{ width: `${promptPct}%`, opacity: 0.65 }}
                    />
                  </div>
                </div>
                <p className="text-[11px] text-[#4a4a4a] mt-0.5">
                  {toTokens(i.prompt)} prompt • {toTokens(i.output)} output
                </p>
              </div>
              {onAdd && (
                <button
                  className="text-xs px-2 py-1 rounded-none border border-[var(--border)] hover:border-[var(--accent)] text-[#c0c0c0]"
                  onClick={() => onAdd(i.label)}
                >
                  + Compare
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function HighlightsTabs({
  active,
  onChange,
}: {
  active: "performance" | "efficiency" | "cost";
  onChange: (v: "performance" | "efficiency" | "cost") => void;
}) {
  return (
    <div className="tab-switch">
      {(["performance", "efficiency", "cost"] as const).map((t) => (
        <button
          key={t}
          className={cn(active === t && "active")}
          onClick={() => {
            onChange(t);
            posthog.capture("highlights_tab_changed", {
              tab: t,
              previous_tab: active,
            });
          }}
        >
          {t === "performance"
            ? "Performance"
            : t === "efficiency"
              ? "Efficiency"
              : "Cost"}
        </button>
      ))}
    </div>
  );
}
