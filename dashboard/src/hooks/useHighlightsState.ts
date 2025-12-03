"use client";

import { useState } from "react";

export type HighlightsTab = "performance" | "efficiency" | "cost";

export function useHighlightsState() {
  const [activeTab, setActiveTab] = useState<HighlightsTab>("performance");
  const [topN, setTopN] = useState(6);
  const [category, setCategory] = useState<string>("all");

  return { activeTab, setActiveTab, topN, setTopN, category, setCategory };
}
