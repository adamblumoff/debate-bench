import { VisualizationSpec } from "vega-embed";
import { PricingSnapshot } from "@/lib/pricing";
import { toPercent } from "@/lib/format";
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
} from "@/lib/specs/highlights";

export type HighlightSpecs = {
  sideBias?: VisualizationSpec;
  judgeSideBiasCv?: VisualizationSpec;
  categoryHeat?: VisualizationSpec;
  tokens?: VisualizationSpec;
  ratingVsWin?: VisualizationSpec;
  h2h?: VisualizationSpec;
  judgeHeat?: VisualizationSpec;
};

export type HighlightLists = {
  elo: { label: string; value: number; hint?: string }[];
  win: { label: string; value: number; hint?: string }[];
  tokens: { label: string; prompt: number; output: number }[];
  cost: { label: string; value: number; hint?: string }[];
  sideBias: { label: string; value: number; hint?: string }[];
};

export type KpiItem = {
  label: string;
  value: string;
  helper?: string;
};

export type Kpi = {
  topModel: KpiItem;
  sideGap: KpiItem;
  judgeSpan: KpiItem;
} | null;

export function selectHighlightDerived(
  derived?: DerivedData,
  derivedByCategory?: Record<string, DerivedData>,
  category: string = "all",
): DerivedData | undefined {
  if (!derived) return undefined;
  if (category === "all") return derived;
  return derivedByCategory?.[category] || derived;
}

export function buildHighlightSpecs(
  highlightDerived?: DerivedData,
  fullDerived?: DerivedData,
  topN: number = 6,
  category: string = "all",
): HighlightSpecs {
  if (!highlightDerived || !fullDerived) return {};
  return {
    sideBias: buildSideBiasSpec(highlightDerived, topN),
    judgeSideBiasCv: buildJudgeSideBiasCvSpec(fullDerived, 3, false),
    categoryHeat: buildCategoryHeatSpec(highlightDerived, category),
    tokens: buildTokenStackSpec(highlightDerived, topN),
    ratingVsWin: buildRatingVsWinSpec(highlightDerived),
    h2h: buildH2HSpec(fullDerived),
    judgeHeat: buildJudgeHeatSpec(fullDerived),
  };
}

export function buildHighlightLists(
  highlightDerived: DerivedData | undefined,
  pricing: PricingSnapshot,
  topN: number = 6,
): HighlightLists {
  if (!highlightDerived) {
    return { elo: [], win: [], tokens: [], cost: [], sideBias: [] };
  }

  const elo = highlightDerived.modelStats.slice(0, topN).map((m) => ({
    label: m.model_id,
    value: m.rating,
    hint: toPercent(m.win_rate),
  }));

  const win = [...highlightDerived.modelStats]
    .sort((a, b) => b.win_rate - a.win_rate)
    .slice(0, topN)
    .map((m) => ({
      label: m.model_id,
      value: m.win_rate,
      hint: `Games ${m.games}`,
    }));

  const tokens = highlightDerived.modelStats.slice(0, topN).map((m) => ({
    label: m.model_id,
    prompt: m.mean_prompt_tokens,
    output: m.mean_completion_tokens,
  }));

  const observedCost = highlightDerived.modelStats
    .filter((m) => typeof m.mean_cost_usd === "number")
    .sort((a, b) => (a.mean_cost_usd ?? 0) - (b.mean_cost_usd ?? 0))
    .slice(0, topN)
    .map((m) => ({
      label: m.model_id,
      value: m.mean_cost_usd ?? 0,
      hint: "Observed avg per turn (USD)",
    }));

  const cost =
    observedCost.length > 0
      ? observedCost
      : (() => {
          const allowedModels = new Set(
            highlightDerived.modelStats.slice(0, topN).map((m) => m.model_id),
          );
          const pricingRows = [...pricing.rows];
          const costPool = pricingRows.filter((r) =>
            allowedModels.has(r.model_id),
          );
          const costSource = costPool.length ? costPool : pricingRows;
          return costSource
            .sort(
              (a, b) =>
                a.input_per_million +
                a.output_per_million -
                (b.input_per_million + b.output_per_million),
            )
            .slice(0, topN)
            .map((r) => ({
              label: r.model_id,
              value: r.input_per_million + r.output_per_million,
              hint: `${pricing.currency} in/out`,
            }));
        })();

  const sideBias = [...highlightDerived.modelStats]
    .map((m) => {
      const gap = (m.pro_win_rate || 0) - (m.con_win_rate || 0);
      return {
        label: m.model_id,
        value: Math.abs(gap),
        hint: `${gap >= 0 ? "+" : ""}${toPercent(gap)} • Pro ${toPercent(m.pro_win_rate)} / Con ${toPercent(m.con_win_rate)}`,
      };
    })
    .sort((a, b) => b.value - a.value)
    .slice(0, topN);

  return { elo, win, tokens, cost, sideBias };
}

export function buildKpis(derived?: DerivedData): Kpi {
  if (!derived || !derived.modelStats.length) return null;
  const top = derived.modelStats[0];
  const widestGap = [...derived.modelStats].sort(
    (a, b) =>
      Math.abs(b.pro_win_rate - b.con_win_rate) -
      Math.abs(a.pro_win_rate - a.con_win_rate),
  )[0];
  const judgeRange = derived.judgeAgreement.reduce(
    (acc, j) => {
      acc.min = Math.min(acc.min, j.agreement_rate);
      acc.max = Math.max(acc.max, j.agreement_rate);
      return acc;
    },
    {
      min: derived.judgeAgreement.length ? 1 : 0,
      max: derived.judgeAgreement.length ? 0 : 0,
    },
  );
  return {
    topModel: {
      label: top.model_id,
      value: toPercent(top.win_rate),
      helper: `${top.games} games`,
    },
    sideGap: {
      label: widestGap.model_id,
      value: toPercent(
        Math.abs(widestGap.pro_win_rate - widestGap.con_win_rate),
      ),
      helper: `Pro ${toPercent(widestGap.pro_win_rate)} / Con ${toPercent(widestGap.con_win_rate)}`,
    },
    judgeSpan: {
      label: "Panel agreement",
      value: `${toPercent(judgeRange.min)} – ${toPercent(judgeRange.max)}`,
      helper: `${derived.judgeAgreement.length} judge pairs`,
    },
  };
}
