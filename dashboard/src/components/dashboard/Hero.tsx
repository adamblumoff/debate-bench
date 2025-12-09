"use client";

export function Hero({
  debateCount,
  modelCount,
}: {
  debateCount: number;
  modelCount: number;
}) {
  return (
    <header className="hero">
      <div className="flex items-center gap-4">
        <div className="logo-pill">DB</div>
        <div>
          <p className="text-[11px] tracking-[0.26em] text-slate-400 uppercase">
            DEBATEBENCH
          </p>
          <h1 className="text-4xl font-semibold text-white display-font">
            Interactive Results Dashboard
          </h1>
          <p className="text-slate-400 text-sm">
            Live benchmarks • {modelCount} models • {debateCount} debates
          </p>
        </div>
      </div>
    </header>
  );
}
