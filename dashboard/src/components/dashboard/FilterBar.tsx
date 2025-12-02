"use client";

type Props = {
  categories: string[];
  category: string;
  onCategory: (v: string) => void;
  topN: number;
  onTopN: (v: number) => void;
};

export function FilterBar({ categories, category, onCategory, topN, onTopN }: Props) {
  return (
    <div className="filter-bar sticky top-0 z-20 backdrop-blur">
      <div className="filter-row">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Category</p>
            <div className="flex gap-2 flex-wrap">
              <button className={`chip ${category === "all" ? "active" : ""}`} onClick={() => onCategory("all")}>
                All
              </button>
              {categories.map((c) => (
                <button key={c} className={`chip ${category === c ? "active" : ""}`} onClick={() => onCategory(c)}>
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Top N</p>
            <div className="flex items-center gap-2">
              <input type="range" min={4} max={12} value={topN} onChange={(e) => onTopN(Number(e.target.value))} />
              <span className="text-sm text-slate-200">{topN}</span>
            </div>
          </div>
        </div>
        <div className="text-xs text-slate-400">
          Filters apply to highlights and category heatmaps; compare state is shareable via URL.
        </div>
      </div>
    </div>
  );
}
