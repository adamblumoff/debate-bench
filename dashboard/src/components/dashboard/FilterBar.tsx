"use client";

type Props = {
  categories: string[];
  category: string;
  onCategory: (v: string) => void;
  topN: number;
  onTopN: (v: number) => void;
  maxTopN?: number;
  defaultTopN?: number;
  onResetFilters?: () => void;
};

export function FilterBar({
  categories,
  category,
  onCategory,
  topN,
  onTopN,
  maxTopN = 12,
  defaultTopN = 6,
  onResetFilters,
}: Props) {
  const sliderMax = Math.max(defaultTopN, maxTopN);
  const clampedTopN = Math.min(topN, sliderMax);
  const hasFilters = category !== "all" || topN !== defaultTopN;

  const handleReset = () => {
    if (onResetFilters) {
      onResetFilters();
      return;
    }
    onCategory("all");
    onTopN(defaultTopN);
  };

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
              <span className="text-[11px] text-slate-500">1</span>
              <input
                type="range"
                min={1}
                max={sliderMax}
                value={clampedTopN}
                onChange={(e) =>
                  onTopN(
                    Math.max(1, Math.min(sliderMax, Number(e.target.value))),
                  )
                }
              />
              <span className="text-[11px] text-slate-500">
                {sliderMax === clampedTopN ? "All" : sliderMax}
              </span>
              <span className="topn-pill">Top {clampedTopN}</span>
            </div>
          </div>
        </div>
        <div className="filter-actions">
          <p className="text-xs text-slate-400 filter-help">
            Filters apply to highlights and category heatmaps; compare state is
            shareable via URL.
          </p>
          <button
            className={`clear-pill ${!hasFilters ? "opacity-50 cursor-not-allowed" : ""}`}
            onClick={handleReset}
            disabled={!hasFilters}
          >
            Clear all
          </button>
        </div>
      </div>
      <div className="filter-row filter-foot">
        <div className="pin-row">
          {hasFilters ? (
            <>
              {category !== "all" && (
                <span className="pill pill-soft">Category: {category}</span>
              )}
              {topN !== defaultTopN && (
                <span className="pill pill-soft">Top {clampedTopN}</span>
              )}
            </>
          ) : (
            <span className="pin-empty">No filters applied.</span>
          )}
        </div>
      </div>
    </div>
  );
}
