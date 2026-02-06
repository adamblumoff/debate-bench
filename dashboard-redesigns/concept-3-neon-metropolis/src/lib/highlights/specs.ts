import { PricingSnapshot } from "@/lib/pricing";
import { DerivedData } from "@/lib/types";
import {
  buildCategoryHeatSpec,
  buildH2HSpec,
  buildJudgeHeatSpec,
  buildJudgeSideBiasCvSpec,
  buildSideBiasSpec,
} from "@/lib/specs/core";
import {
  buildRatingVsWinSpec,
  buildTokenStackSpec,
  buildPricePerfSpec,
  PricePerfMetric,
} from "@/lib/specs/highlights";
import { HighlightSpecs } from "./types";

export function buildHighlightSpecs(
  highlightDerived: DerivedData | undefined,
  fullDerived: DerivedData | undefined,
  pricing: PricingSnapshot,
  pricePerfMetric: PricePerfMetric,
  topN: number = 6,
  selectedCategories: string[] = [],
): HighlightSpecs {
  if (!highlightDerived || !fullDerived) return {};
  return {
    sideBias: buildSideBiasSpec(highlightDerived, topN),
    judgeSideBiasCv: buildJudgeSideBiasCvSpec(fullDerived, 3, false),
    categoryHeat: buildCategoryHeatSpec(highlightDerived, selectedCategories),
    tokens: buildTokenStackSpec(highlightDerived, topN),
    ratingVsWin: buildRatingVsWinSpec(highlightDerived),
    pricePerf: buildPricePerfSpec(highlightDerived, pricing, pricePerfMetric),
    h2h: buildH2HSpec(fullDerived),
    judgeHeat: buildJudgeHeatSpec(fullDerived),
  };
}
