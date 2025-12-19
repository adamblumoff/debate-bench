"use client";

import { useMemo, useState, useRef, useEffect, useCallback } from "react";
import { ChevronDown } from "lucide-react";

type Props = {
  categories: string[];
  selectedCategories: string[];
  onCategories: (v: string[]) => void;
  models: string[];
  selectedModels: string[];
  onModels: (v: string[]) => void;
  onResetFilters?: () => void;
};

export function FilterBar({
  categories,
  selectedCategories,
  onCategories,
  models,
  selectedModels,
  onModels,
  onResetFilters,
}: Props) {
  const [categorySearch, setCategorySearch] = useState("");
  const [modelSearch, setModelSearch] = useState("");
  const [openMenu, setOpenMenu] = useState<"category" | "models" | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const hasFilters = selectedCategories.length > 0 || selectedModels.length > 0;

  const closeMenus = useCallback(() => setOpenMenu(null), []);

  useEffect(() => {
    const onDocMouseDown = (e: MouseEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target as Node)) {
        closeMenus();
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeMenus();
    };
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [closeMenus]);

  const filteredModels = useMemo(() => {
    if (!modelSearch.trim()) return models;
    const q = modelSearch.toLowerCase();
    return models.filter((m) => m.toLowerCase().includes(q));
  }, [models, modelSearch]);

  const filteredCategories = useMemo(() => {
    if (!categorySearch.trim()) return categories;
    const q = categorySearch.toLowerCase();
    return categories.filter((c) => c.toLowerCase().includes(q));
  }, [categories, categorySearch]);

  const toggleModel = (id: string) => {
    if (selectedModels.includes(id)) {
      onModels(selectedModels.filter((m) => m !== id));
      return;
    }
    onModels([...selectedModels, id]);
  };

  const toggleCategory = (id: string) => {
    if (selectedCategories.includes(id)) {
      onCategories(selectedCategories.filter((c) => c !== id));
      return;
    }
    onCategories([...selectedCategories, id]);
  };

  const handleReset = () => {
    if (onResetFilters) {
      onResetFilters();
      return;
    }
    onCategories([]);
    onModels([]);
  };

  const categorySummary =
    selectedCategories.length === 0
      ? "All categories"
      : selectedCategories.length === 1
        ? selectedCategories[0]
        : `${selectedCategories.length} categories selected`;

  const modelSummary =
    selectedModels.length === 0
      ? "All models"
      : selectedModels.length === 1
        ? selectedModels[0]
        : `${selectedModels.length} models selected`;

  return (
    <div ref={rootRef} className="filter-bar sticky top-0 z-20 backdrop-blur">
      <div className="filter-row">
        <div className="flex flex-wrap items-start gap-3">
          <div className="category-block relative">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400 category-label">
              Category
            </p>
            <details className="relative">
              <summary className="filter-summary bg-[var(--card)] border border-[var(--border)] rounded-md px-2.5 py-2 text-sm text-slate-100 cursor-pointer select-none min-w-[220px] flex items-center justify-between gap-2">
                <span className="truncate">{categorySummary}</span>
                <ChevronDown
                  className="h-4 w-4 text-slate-100 flex-shrink-0"
                  aria-hidden="true"
                />
              </summary>
              <button
                type="button"
                className="absolute inset-0"
                aria-label="Toggle category menu"
                onClick={(e) => {
                  e.preventDefault();
                  setOpenMenu((v) => (v === "category" ? null : "category"));
                }}
              />
              {openMenu === "category" && (
                <div className="absolute right-0 mt-2 w-[220px] rounded-md border border-[var(--border)] bg-[var(--card)] p-3 shadow-lg z-40">
                  <input
                    type="search"
                    placeholder="Search categories"
                    value={categorySearch}
                    onChange={(e) => setCategorySearch(e.target.value)}
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      type="button"
                      className="text-xs px-3 py-1.5 rounded-md border border-[var(--border)] text-slate-200"
                      onClick={() => onCategories(categories)}
                    >
                      Select all
                    </button>
                    <button
                      type="button"
                      className="text-xs px-3 py-1.5 rounded-md border border-[var(--border)] text-slate-200"
                      onClick={() => onCategories([])}
                    >
                      Clear
                    </button>
                  </div>
                  <div className="max-h-56 overflow-auto border border-[var(--border)] rounded-md p-2 mt-2 space-y-1">
                    {filteredCategories.map((c) => {
                      const checked = selectedCategories.includes(c);
                      return (
                        <label
                          key={c}
                          className="flex items-center gap-2 text-sm text-slate-200"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleCategory(c)}
                          />
                          <span className={checked ? "text-white" : ""}>
                            {c}
                          </span>
                        </label>
                      );
                    })}
                    {filteredCategories.length === 0 && (
                      <p className="text-xs text-slate-500 px-1 py-2">
                        No categories match this search.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </details>
          </div>

          <div className="category-block relative">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400 category-label">
              Models
            </p>
            <details className="relative">
              <summary className="filter-summary bg-[var(--card)] border border-[var(--border)] rounded-md px-2.5 py-2 text-sm text-slate-100 cursor-pointer select-none min-w-[220px] flex items-center justify-between gap-2">
                <span className="truncate">{modelSummary}</span>
                <ChevronDown
                  className="h-4 w-4 text-slate-100 flex-shrink-0"
                  aria-hidden="true"
                />
              </summary>
              <button
                type="button"
                className="absolute inset-0"
                aria-label="Toggle models menu"
                onClick={(e) => {
                  e.preventDefault();
                  setOpenMenu((v) => (v === "models" ? null : "models"));
                }}
              />
              {openMenu === "models" && (
                <div className="absolute right-0 mt-2 w-[220px] rounded-md border border-[var(--border)] bg-[var(--card)] p-3 shadow-lg z-40">
                  <input
                    type="search"
                    placeholder="Search models"
                    value={modelSearch}
                    onChange={(e) => setModelSearch(e.target.value)}
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      type="button"
                      className="text-xs px-3 py-1.5 rounded-md border border-[var(--border)] text-slate-200"
                      onClick={() => onModels(models)}
                    >
                      Select all
                    </button>
                    <button
                      type="button"
                      className="text-xs px-3 py-1.5 rounded-md border border-[var(--border)] text-slate-200"
                      onClick={() => onModels([])}
                    >
                      Clear
                    </button>
                  </div>
                  <div className="max-h-56 overflow-auto border border-[var(--border)] rounded-md p-2 mt-2 space-y-1">
                    {filteredModels.map((m) => {
                      const checked = selectedModels.includes(m);
                      return (
                        <label
                          key={m}
                          className="flex items-center gap-2 text-sm text-slate-200"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleModel(m)}
                          />
                          <span className={checked ? "text-white" : ""}>
                            {m}
                          </span>
                        </label>
                      );
                    })}
                    {filteredModels.length === 0 && (
                      <p className="text-xs text-slate-500 px-1 py-2">
                        No models match this search.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </details>
          </div>
        </div>
        <div className="filter-actions">
          <p className="text-xs text-slate-400 filter-help">
            Filters apply to all dashboard charts.
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
              {selectedCategories.length > 0 && (
                <span className="pill pill-soft">
                  Categories:{" "}
                  {selectedCategories.length <= 3
                    ? selectedCategories.join(", ")
                    : `${selectedCategories.length} selected`}
                </span>
              )}
              {selectedModels.length > 0 && (
                <span className="pill pill-soft">
                  Models:{" "}
                  {selectedModels.length <= 3
                    ? selectedModels.join(", ")
                    : `${selectedModels.length} selected`}
                </span>
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
