"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";

export function Hero({
  debateCount,
  modelCount,
}: {
  debateCount: number;
  modelCount: number;
}) {
  const searchParams = useSearchParams();
  const builderHref = useMemo(() => {
    const params = new URLSearchParams();
    searchParams.getAll("compare").forEach((v) => params.append("compare", v));
    const run = searchParams.get("run");
    if (run) params.set("run", run);
    const qs = params.toString();
    return qs ? `/builder?${qs}` : "/builder";
  }, [searchParams]);
  return (
    <header className="hero">
      <div className="flex items-center gap-4">
        <div className="logo-pill">DB</div>
        <div>
          <p className="text-xs tracking-[0.28em] text-slate-400">
            DEBATEBENCH
          </p>
          <h1 className="text-4xl font-semibold text-white">
            Interactive Results Dashboard
          </h1>
          <p className="text-slate-400 text-sm">
            Live benchmarks • {modelCount} models • {debateCount} debates
          </p>
        </div>
      </div>
      <div className="hero-cta">
        <Link href={builderHref} className="btn-primary">
          Custom chart
        </Link>
      </div>
    </header>
  );
}
