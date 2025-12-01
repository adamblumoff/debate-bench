"use client";

import { ReactNode } from "react";

export function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode; }) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white/80 p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/70">
      <header className="mb-3">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{title}</h2>
        {subtitle && <p className="text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</p>}
      </header>
      <div className="min-h-[260px]">{children}</div>
    </section>
  );
}
