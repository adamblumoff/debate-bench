"use client";

type Props = {
  categories: string[];
  category: string;
  onCategory: (v: string) => void;
  topN: number;
  onTopN: (v: number) => void;
};

export function FilterBar({
  categories,
  category,
  onCategory,
  topN,
  onTopN,
}: Props) {
  return (
    <div className="filter-bar sticky top-0 z-20 backdrop-blur">
      <div className="filter-row">
        <div className="flex flex-wrap items-start gap-3">
          <div className="category-block">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400 category-label">
              Category
            </p>
            <div className="chip-row">
              <button
                className={`chip ${category === "all" ? "active" : ""}`}
                onClick={() => onCategory("all")}
              >
                All
              </button>
              {categories.map((c) => (
                <button
                  key={c}
                  className={`chip ${category === c ? "active" : ""}`}
                  onClick={() => onCategory(c)}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div className="topn-block">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400 topn-label">
              Top N
            </p>
            <div className="topn-slider">
              <input
                type="range"
                min={4}
                max={12}
                value={topN}
                onChange={(e) => onTopN(Number(e.target.value))}
              />
              <span className="text-sm text-slate-200">{topN}</span>
            </div>
          </div>
        </div>
        <div className="text-xs text-slate-400 filter-help">
          Filters apply to highlights and category heatmaps; compare state is
          shareable via URL.
        </div>
      </div>
    </div>
  );
}
