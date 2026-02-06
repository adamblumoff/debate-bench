"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function ChartCard({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("card chart-card", className)}>
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-light text-[var(--text-primary)] text-balance tracking-[0.02em]">
            {title}
          </h2>
          {subtitle && <p className="text-sm text-[var(--text-muted)]">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          <span className="chart-legend-bar" />
        </div>
      </header>
      <div className="min-h-[260px] overflow-x-auto">{children}</div>
    </section>
  );
}
