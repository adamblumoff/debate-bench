"use client";

import { useMemo, useState, useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";
import * as Popover from "@radix-ui/react-popover";
import posthog from "posthog-js";
import { cn } from "@/lib/cn";

type Props = {
  categories: string[];
  selectedCategories: string[];
  onCategories: (v: string[]) => void;
  models: string[];
  selectedModels: string[];
  onModels: (v: string[]) => void;
  onResetFilters?: () => void;
};

type FilterMenuProps = {
  label: string;
  summary: string;
  items: string[];
  selected: string[];
  searchValue: string;
  onSearchChange: (value: string) => void;
  onToggle: (id: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
  emptyMessage: string;
  align?: "start" | "center" | "end";
  sideOffset?: number;
};

function FilterMenu({
  label,
  summary,
  items,
  selected,
  searchValue,
  onSearchChange,
  onToggle,
  onSelectAll,
  onClear,
  emptyMessage,
  align = "start",
  sideOffset = 8,
}: FilterMenuProps) {
  return (
    <div className="category-block relative">
      <p className="text-xs uppercase text-[var(--text-muted)] category-label">{label}</p>
      <Popover.Root>
        <Popover.Trigger asChild>
          <button
            type="button"
            className="filter-summary bg-[var(--card)] border border-[var(--border)] rounded-none px-2.5 py-2 text-sm text-[var(--text-primary)] cursor-pointer select-none min-w-[220px] flex items-center justify-between gap-2"
            aria-label={`Open ${label.toLowerCase()} filter menu`}
          >
            <span className="truncate">{summary}</span>
            <ChevronDown
              className="h-4 w-4 text-[var(--text-primary)] flex-shrink-0"
              aria-hidden="true"
            />
          </button>
        </Popover.Trigger>
        <Popover.Content
          align={align}
          sideOffset={sideOffset}
          className="z-40 mt-2 w-[220px] rounded-none border border-[var(--border)] bg-[var(--card)] p-3 shadow-lg outline-none"
        >
          <div className="flex flex-col gap-2">
            <input
              type="search"
              placeholder={`Search ${label.toLowerCase()}`}
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full rounded-none border border-[var(--border)] bg-[var(--bg-surface)] p-2 text-sm"
            />
            <div className="flex gap-2">
              <button
                type="button"
                className="text-xs px-3 py-1.5 rounded-none border border-[var(--border)] text-[#c0c0ee]"
                onClick={onSelectAll}
              >
                Select all
              </button>
              <button
                type="button"
                className="text-xs px-3 py-1.5 rounded-none border border-[var(--border)] text-[#c0c0ee]"
                onClick={onClear}
              >
                Clear
              </button>
            </div>
            <div className="max-h-56 overflow-auto border border-[var(--border)] rounded-none p-2 space-y-1">
              {items.map((id) => {
                const checked = selected.includes(id);
                return (
                  <label
                    key={id}
                    className="flex items-center gap-2 text-sm text-[#c0c0ee]"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggle(id)}
                    />
                    <span className={cn(checked && "text-[var(--text-primary)]")}>{id}</span>
                  </label>
                );
              })}
              {items.length === 0 && (
                <p className="text-xs text-[#585888] px-1 py-2">
                  {emptyMessage}
                </p>
              )}
            </div>
          </div>
        </Popover.Content>
      </Popover.Root>
    </div>
  );
}

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
  const [isStuck, setIsStuck] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const hasFilters = selectedCategories.length > 0 || selectedModels.length > 0;

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
      const next = selectedModels.filter((m) => m !== id);
      onModels(next);
      posthog.capture("model_filter_changed", {
        action: "removed",
        model_id: id,
        selected_count: next.length,
      });
      return;
    }
    const next = [...selectedModels, id];
    onModels(next);
    posthog.capture("model_filter_changed", {
      action: "added",
      model_id: id,
      selected_count: next.length,
    });
  };

  const toggleCategory = (id: string) => {
    if (selectedCategories.includes(id)) {
      const next = selectedCategories.filter((c) => c !== id);
      onCategories(next);
      posthog.capture("category_filter_changed", {
        action: "removed",
        category: id,
        selected_count: next.length,
      });
      return;
    }
    const next = [...selectedCategories, id];
    onCategories(next);
    posthog.capture("category_filter_changed", {
      action: "added",
      category: id,
      selected_count: next.length,
    });
  };

  const handleReset = () => {
    posthog.capture("filters_reset", {
      previous_categories_count: selectedCategories.length,
      previous_models_count: selectedModels.length,
    });
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

  useEffect(() => {
    const updateStuck = () => {
      const el = rootRef.current;
      if (!el) return;
      const top = el.getBoundingClientRect().top;
      setIsStuck(top <= 0);
    };
    updateStuck();
    window.addEventListener("scroll", updateStuck, { passive: true });
    window.addEventListener("resize", updateStuck);
    return () => {
      window.removeEventListener("scroll", updateStuck);
      window.removeEventListener("resize", updateStuck);
    };
  }, []);

  return (
    <div ref={rootRef} className={cn("filter-bar", isStuck && "is-stuck")}>
      <div className="filter-row">
        <div className="flex flex-wrap items-start gap-3">
          <FilterMenu
            label="Category"
            summary={categorySummary}
            items={filteredCategories}
            selected={selectedCategories}
            searchValue={categorySearch}
            onSearchChange={setCategorySearch}
            onToggle={toggleCategory}
            onSelectAll={() => onCategories(categories)}
            onClear={() => onCategories([])}
            emptyMessage="No categories match this search."
          />

          <FilterMenu
            label="Models"
            summary={modelSummary}
            items={filteredModels}
            selected={selectedModels}
            searchValue={modelSearch}
            onSearchChange={setModelSearch}
            onToggle={toggleModel}
            onSelectAll={() => onModels(models)}
            onClear={() => onModels([])}
            emptyMessage="No models match this search."
          />
        </div>

        <div className="filter-actions">
          {hasFilters && (
            <button
              type="button"
              className="clear-pill"
              onClick={handleReset}
            >
              Clear filters
            </button>
          )}
          <div className="run-toolbar">
            <span className="run-chip">Filters</span>
            <div className="run-meta-inline">
              <span className="run-chip">{categorySummary}</span>
              <span className="run-chip">{modelSummary}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
