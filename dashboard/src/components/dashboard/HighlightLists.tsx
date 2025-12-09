"use client";

import { toTokens } from "@/lib/format";

export function MiniBarList({
  title,
  items,
  formatter,
  onAdd,
  expected,
}: {
  title: string;
  items: { label: string; value: number; hint?: string }[];
  formatter: (n: number) => string;
  onAdd?: (id: string) => void;
  expected?: number;
}) {
  const desired = expected !== undefined ? expected : items.length;
  const rowHeight = 56;
  const minHeight = desired ? desired * rowHeight : undefined;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="card flex-1">
      <header className="flex items-center justify-between mb-2">
        <p className="text-sm text-slate-300">{title}</p>
        <div className="h-1 w-10 rounded-full bg-[var(--accent)]" />
      </header>
      <div className="space-y-2" style={minHeight ? { minHeight } : undefined}>
        {items.map((i) => (
          <div key={i.label} className="flex items-center gap-3">
            <div className="w-full">
              <div className="flex justify-between text-xs text-slate-400">
                <span>{i.label}</span>
                <span className="text-slate-200">{formatter(i.value)}</span>
              </div>
              <div className="h-2.5 rounded-full bg-slate-800/70 overflow-hidden">
                <div
                  className="h-full rounded-full bg-[var(--accent)]"
                  style={{ width: `${Math.max((i.value / max) * 100, 4)}%` }}
                />
              </div>
              {i.hint && (
                <p className="text-[11px] text-slate-500 mt-0.5">{i.hint}</p>
              )}
            </div>
            {onAdd && (
              <button
                className="text-xs px-2 py-1 rounded-md border border-[var(--border)] hover:border-[var(--accent)] text-slate-200"
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
}: {
  title: string;
  items: { label: string; prompt: number; output: number }[];
  onAdd?: (id: string) => void;
}) {
  const max = Math.max(...items.map((i) => i.prompt + i.output), 1);
  return (
    <div className="card flex-1">
      <header className="flex items-center justify-between mb-2">
        <p className="text-sm text-slate-300">{title}</p>
        <div className="h-1 w-10 rounded-full bg-[var(--accent)]" />
      </header>
      <div className="space-y-2">
        {items.map((i) => {
          const total = i.prompt + i.output;
          const promptPct = total ? (i.prompt / total) * 100 : 50;
          return (
            <div key={i.label} className="flex items-center gap-3">
              <div className="w-full">
                <div className="flex justify-between text-xs text-slate-400">
                  <span>{i.label}</span>
                  <span className="text-slate-200">{toTokens(total)}</span>
                </div>
                <div className="h-2.5 rounded-full bg-slate-800/70 overflow-hidden flex">
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
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {toTokens(i.prompt)} prompt • {toTokens(i.output)} output
                </p>
              </div>
              {onAdd && (
                <button
                  className="text-xs px-2 py-1 rounded-md border border-[var(--border)] hover:border-[var(--accent)] text-slate-200"
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
          className={active === t ? "active" : ""}
          onClick={() => onChange(t)}
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
