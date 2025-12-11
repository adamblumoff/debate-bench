"use client";

import { useState } from "react";

export type HighlightsTab = "performance" | "efficiency" | "cost";

export function useHighlightsState() {
  const [activeTab, setActiveTab] = useState<HighlightsTab>("performance");
  const [categories, setCategories] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);

  return {
    activeTab,
    setActiveTab,
    categories,
    setCategories,
    models,
    setModels,
  };
}
