import { PricingSnapshot } from "@/lib/pricing";
import { toPercent } from "@/lib/format";
import { DerivedData } from "@/lib/types";
import { HighlightLists } from "./types";

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

  const observedCostPerMillion = highlightDerived.modelStats
    .filter(
      (m) =>
        typeof m.mean_cost_usd === "number" &&
        typeof m.mean_total_tokens === "number" &&
        m.mean_total_tokens > 0,
    )
    .map((m) => {
      const perMillion =
        ((m.mean_cost_usd ?? 0) / (m.mean_total_tokens || 1)) * 1_000_000;
      const hintParts: string[] = ["Observed effective (USD/1M)"];
      if (typeof m.cost_samples === "number")
        hintParts.push(`${m.cost_samples} turns`);
      return {
        label: m.model_id,
        value: perMillion,
        hint: hintParts.join(" • "),
      };
    })
    .sort((a, b) => a.value - b.value)
    .slice(0, topN);

  const cost =
    observedCostPerMillion.length > 0
      ? observedCostPerMillion
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
              hint: `${pricing.currency} in+out (snapshot)`,
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
