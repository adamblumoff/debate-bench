type Props = {
  kpi: { topModel: string; sideGap: string; judgeSpan: string } | null;
};

export function KpiStrip({ kpi }: Props) {
  if (!kpi) return null;
  return (
    <section id="overview" className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="kpi-tile">
          <p className="text-xs uppercase tracking-wide text-slate-400">Top model</p>
          <p className="text-lg font-semibold text-white">{kpi.topModel}</p>
        </div>
        <div className="kpi-tile">
          <p className="text-xs uppercase tracking-wide text-slate-400">Widest side gap</p>
          <p className="text-lg font-semibold text-white">{kpi.sideGap}</p>
        </div>
        <div className="kpi-tile">
          <p className="text-xs uppercase tracking-wide text-slate-400">Judge agreement span</p>
          <p className="text-lg font-semibold text-white">{kpi.judgeSpan}</p>
        </div>
      </div>
    </section>
  );
}
