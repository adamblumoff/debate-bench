"use client";

export function Hero({ debateCount, modelCount }: { debateCount: number; modelCount: number }) {
  return (
    <header className="hero">
      <div className="flex items-center gap-4">
        <div className="logo-pill">DB</div>
        <div>
          <p className="text-xs tracking-[0.28em] text-slate-400">DEBATEBENCH</p>
          <h1 className="text-4xl font-semibold text-white">Interactive Results Dashboard</h1>
          <p className="text-slate-400 text-sm">Live benchmarks • {modelCount} models • {debateCount} debates</p>
        </div>
      </div>
      <div className="hero-cta">
        <a href="#builder" className="btn-primary">Custom chart</a>
      </div>
    </header>
  );
}
