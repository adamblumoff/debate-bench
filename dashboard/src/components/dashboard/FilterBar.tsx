"use client";

type Props = {
  categories: string[];
  category: string;
  onCategory: (v: string) => void;
  onResetFilters?: () => void;
};

export function FilterBar({
  categories,
  category,
  onCategory,
  onResetFilters,
}: Props) {
  const hasFilters = category !== "all";

  const handleReset = () => {
    if (onResetFilters) {
      onResetFilters();
      return;
    }
    onCategory("all");
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
        </div>
        <div className="filter-actions">
          <p className="text-xs text-slate-400 filter-help">
            Filters apply to highlights and category heatmaps.
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
            </>
          ) : (
            <span className="pin-empty">No filters applied.</span>
          )}
        </div>
      </div>
    </div>
  );
}
