type Props = {
  kpi: {
    topModel: { label: string; value: string; helper?: string };
    sideGap: { label: string; value: string; helper?: string };
    judgeSpan: { label: string; value: string; helper?: string };
  } | null;
};

export function KpiStrip({ kpi }: Props) {
  if (!kpi) return null;
  const tiles = [
    { title: "Top model", ...kpi.topModel },
    { title: "Widest side gap", ...kpi.sideGap },
    { title: "Judge agreement span", ...kpi.judgeSpan },
  ] as const;
  return (
    <section id="overview" className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        {tiles.map((t) => (
          <div className="kpi-tile" key={t.title}>
            <p className="kpi-label">{t.title}</p>
            <p className="kpi-value monospace">{t.value}</p>
            <div className="flex items-center justify-between text-sm text-slate-200">
              <span className="font-semibold">{t.label}</span>
              {t.helper && <span className="kpi-helper">{t.helper}</span>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
