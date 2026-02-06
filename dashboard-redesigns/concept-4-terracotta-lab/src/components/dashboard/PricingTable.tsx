"use client";

import { PricingSnapshot } from "@/lib/pricing";

export function PricingTable({
  pricing,
  onAdd,
}: {
  pricing: PricingSnapshot;
  onAdd?: (id: string) => void;
}) {
  const showActions = Boolean(onAdd);
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-xs uppercase text-[var(--text-muted)]">
            Pricing
          </p>
          <h3 className="text-lg font-semibold text-[var(--text-primary)] text-balance">
            Cost per 1M tokens
          </h3>
          <p className="text-xs text-[#b8a898]">
            {pricing.source === "live" ? "Live" : "Snapshot"} updated{" "}
            {pricing.updated} ({pricing.currency})
          </p>
        </div>
        <span className="pill">
          {pricing.source === "live" ? "Live" : "Snapshot"}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm tabular-nums">
          <thead className="text-[var(--text-muted)]">
            <tr>
              <th className="py-2 pr-4 text-left">Model</th>
              <th className="py-2 pr-4 text-left">Provider</th>
              <th className="py-2 pr-4 text-right">Input</th>
              <th className="py-2 pr-4 text-right">Output</th>
              {showActions && <th className="py-2 pr-4 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody className="text-[#4a3e30]">
            {pricing.rows.map((r) => (
              <tr
                key={r.model_id}
                className="border-t border-[var(--border)]/60"
              >
                <td className="py-2 pr-4">{r.model_id}</td>
                <td className="py-2 pr-4 text-[var(--text-muted)]">{r.provider}</td>
                <td className="py-2 pr-4 text-right">
                  ${r.input_per_million.toFixed(2)}
                </td>
                <td className="py-2 pr-4 text-right">
                  ${r.output_per_million.toFixed(2)}
                </td>
                {showActions && (
                  <td className="py-2 pr-4 text-right">
                    <button
                      className="text-xs px-2 py-1 rounded-2xl border border-[var(--border)] hover:border-[var(--accent)]"
                      onClick={() => onAdd?.(r.model_id)}
                    >
                      + Compare
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
