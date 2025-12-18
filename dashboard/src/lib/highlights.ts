import { VisualizationSpec } from "vega-embed";
import { PricingSnapshot } from "@/lib/pricing";
import { toPercent } from "@/lib/format";
import {
  DerivedData,
  JudgeAgreementRow,
  JudgeBiasRow,
  JudgeRowForBuilder,
  ModelStats,
  Winner,
} from "@/lib/types";
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

export type HighlightSpecs = {
  sideBias?: VisualizationSpec;
  judgeSideBiasCv?: VisualizationSpec;
  categoryHeat?: VisualizationSpec;
  tokens?: VisualizationSpec;
  ratingVsWin?: VisualizationSpec;
  pricePerf?: VisualizationSpec;
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
  selectedCategories: string[] = [],
): DerivedData | undefined {
  if (!derived) return undefined;
  if (!selectedCategories.length) return derived;
  if (selectedCategories.length === 1) {
    const category = selectedCategories[0];
    return derivedByCategory?.[category] || derived;
  }
  if (derivedByCategory) {
    const merged = mergeDerivedByCategories(derived, derivedByCategory, selectedCategories);
    if (merged) return merged;
  }
  return filterDerivedByCategories(derived, selectedCategories);
}

export function mergeDerivedByCategories(
  base: DerivedData,
  derivedByCategory: Record<string, DerivedData>,
  selectedCategories: string[],
): DerivedData | null {
  const cats = selectedCategories.filter((c) => derivedByCategory[c]);
  if (!cats.length) return null;
  const parts = cats.map((c) => derivedByCategory[c]);

  const dimSet = new Set<string>();
  for (const p of parts) p.dimensions.forEach((d) => dimSet.add(d));
  const dimensions = Array.from(dimSet).sort();

  const modelSet = new Set<string>();
  for (const p of parts) p.models.forEach((m) => modelSet.add(m));
  const models = Array.from(modelSet).sort();

  // Merge model stats by summing counts and weighting means by games.
  const statsMap = new Map<string, ModelStats>();
  for (const p of parts) {
    for (const s of p.modelStats) {
      const cur = statsMap.get(s.model_id);
      if (!cur) {
        statsMap.set(s.model_id, { ...s });
        continue;
      }
      const prevGames = cur.games || 0;
      const nextGames = s.games || 0;
      const totalGames = prevGames + nextGames;
      cur.wins += s.wins;
      cur.losses += s.losses;
      cur.ties += s.ties;
      cur.games = totalGames;
      cur.pro_games += s.pro_games;
      cur.con_games += s.con_games;
      const wAvg = (a: number, b: number) =>
        totalGames ? (a * prevGames + b * nextGames) / totalGames : b;
      cur.mean_prompt_tokens = wAvg(
        cur.mean_prompt_tokens,
        s.mean_prompt_tokens,
      );
      cur.mean_completion_tokens = wAvg(
        cur.mean_completion_tokens,
        s.mean_completion_tokens,
      );
      cur.mean_total_tokens = wAvg(
        cur.mean_total_tokens,
        s.mean_total_tokens,
      );
      cur.win_rate =
        totalGames ? (cur.wins + 0.5 * cur.ties) / totalGames : cur.win_rate;
      cur.pro_win_rate = cur.pro_games
        ? (cur.wins + 0.5 * cur.ties) / cur.pro_games
        : cur.pro_win_rate;
      cur.con_win_rate = cur.con_games
        ? (cur.wins + 0.5 * cur.ties) / cur.con_games
        : cur.con_win_rate;
      cur.rating = wAvg(cur.rating, s.rating);
      if (typeof s.mean_cost_usd === "number") {
        const prevSamples = cur.cost_samples ?? prevGames;
        const nextSamples = s.cost_samples ?? nextGames;
        const totalSamples = prevSamples + nextSamples;
        if (totalSamples) {
          const prevCost = (cur.mean_cost_usd ?? 0) * prevSamples;
          const nextCost = (s.mean_cost_usd ?? 0) * nextSamples;
          cur.mean_cost_usd = (prevCost + nextCost) / totalSamples;
          cur.cost_samples = totalSamples;
          cur.total_cost_usd =
            (cur.total_cost_usd ?? prevCost) + (s.total_cost_usd ?? nextCost);
        }
      }
    }
  }
  const modelStats = Array.from(statsMap.values()).sort(
    (a, b) => b.rating - a.rating,
  );

  // Merge head-to-head by summing samples and weighted win_rate.
  const h2hMap = new Map<string, { row: string; col: string; win: number; samples: number }>();
  for (const p of parts) {
    for (const cell of p.headToHead) {
      const key = `${cell.row}|||${cell.col}`;
      const cur = h2hMap.get(key);
      if (!cur) {
        h2hMap.set(key, {
          row: cell.row,
          col: cell.col,
          win: cell.win_rate * cell.samples,
          samples: cell.samples,
        });
        continue;
      }
      cur.win += cell.win_rate * cell.samples;
      cur.samples += cell.samples;
    }
  }
  const headToHead = Array.from(h2hMap.values()).map((v) => ({
    row: v.row,
    col: v.col,
    samples: v.samples,
    win_rate: v.samples ? v.win / v.samples : 0,
  }));

  const topicWinrates = parts.flatMap((p) => p.topicWinrates);
  const judgeAgreement = base.judgeAgreement;
  const judgeBias = parts.flatMap((p) => p.judgeBias);
  const debateRows = parts.flatMap((p) => p.debateRows);
  const judgeRows = parts.flatMap((p) => p.judgeRows);

  return {
    models,
    dimensions,
    modelStats,
    headToHead,
    topicWinrates,
    judgeAgreement,
    judgeBias,
    debateRows,
    judgeRows,
  };
}

export function filterDerivedByCategories(
  derived: DerivedData,
  selectedCategories: string[],
): DerivedData {
  if (!selectedCategories.length) return derived;
  const allowed = new Set(selectedCategories);
  return {
    ...derived,
    topicWinrates: derived.topicWinrates.filter(
      (t) => t.category && allowed.has(t.category),
    ),
    judgeBias: derived.judgeBias.filter((j) => allowed.has(j.category)),
    debateRows: derived.debateRows.filter(
      (r) => r.category && allowed.has(r.category),
    ),
    judgeRows: derived.judgeRows.filter(
      (r) => r.category && allowed.has(r.category),
    ),
  };
}

export function filterDerivedByModels(
  derived: DerivedData,
  selectedModels: string[],
): DerivedData {
  if (!selectedModels.length) return derived;
  const allowed = new Set(selectedModels);
  return {
    ...derived,
    models: derived.models.filter((m) => allowed.has(m)),
    modelStats: derived.modelStats.filter((m) => allowed.has(m.model_id)),
    headToHead: derived.headToHead.filter(
      (c) => allowed.has(c.row) && allowed.has(c.col),
    ),
    topicWinrates: derived.topicWinrates.filter((t) =>
      allowed.has(t.model_id),
    ),
    judgeAgreement: derived.judgeAgreement.filter(
      (j) => allowed.has(j.judge_a) && allowed.has(j.judge_b),
    ),
    judgeBias: derived.judgeBias.filter((j) => allowed.has(j.judge_id)),
    debateRows: derived.debateRows.filter(
      (r) => allowed.has(r.pro_model_id) || allowed.has(r.con_model_id),
    ),
    judgeRows: derived.judgeRows.filter(
      (r) => allowed.has(r.pro_model_id) || allowed.has(r.con_model_id),
    ),
  };
}

export function recomputeJudgeMetrics(
  judgeRows: JudgeRowForBuilder[],
): { judgeAgreement: JudgeAgreementRow[]; judgeBias: JudgeBiasRow[] } {
  if (!judgeRows.length) return { judgeAgreement: [], judgeBias: [] };

  const rowsByDebate = new Map<string, JudgeRowForBuilder[]>();
  for (const jr of judgeRows) {
    const debateId = (jr as Record<string, unknown>).debate_id;
    const key = debateId ? String(debateId) : String(jr.topic_id);
    if (!rowsByDebate.has(key)) rowsByDebate.set(key, []);
    rowsByDebate.get(key)!.push(jr);
  }

  const agreePairs = new Map<string, { agree: number; total: number }>();
  const pairKey = (a: string, b: string) => `${a}|||${b}`;
  for (const group of rowsByDebate.values()) {
    const winnersByJudge: Record<string, Winner> = {};
    for (const jr of group) {
      if (!jr.judge_id) continue;
      winnersByJudge[jr.judge_id] = jr.winner;
    }
    const panelJudgeIds = Object.keys(winnersByJudge);
    for (let i = 0; i < panelJudgeIds.length; i++) {
      for (let k = i + 1; k < panelJudgeIds.length; k++) {
        const a = panelJudgeIds[i];
        const b = panelJudgeIds[k];
        const key = pairKey(a, b);
        const entry = agreePairs.get(key) || { agree: 0, total: 0 };
        entry.total += 1;
        if (winnersByJudge[a] === winnersByJudge[b]) entry.agree += 1;
        agreePairs.set(key, entry);
      }
    }
  }

  const judgeAgreement: JudgeAgreementRow[] = Array.from(
    agreePairs.entries(),
  )
    .map(([key, val]) => {
      const [a, b] = key.split("|||");
      return {
        judge_a: a,
        judge_b: b,
        agreement_rate: val.total ? val.agree / val.total : 0,
        samples: val.total,
      };
    })
    .sort(
      (a, b) =>
        a.judge_a.localeCompare(b.judge_a) ||
        a.judge_b.localeCompare(b.judge_b),
    );

  const biasCounts = new Map<
    string,
    { pro: number; con: number; tie: number; category: string; topic_id: string }
  >();
  for (const jr of judgeRows) {
    if (!jr.judge_id || !jr.topic_id) continue;
    const category = (jr.category as string) || "uncategorized";
    const key = `${jr.judge_id}|||${jr.topic_id}`;
    const entry =
      biasCounts.get(key) || {
        pro: 0,
        con: 0,
        tie: 0,
        category,
        topic_id: jr.topic_id,
      };
    entry.category = category;
    if (jr.winner === "pro") entry.pro += 1;
    else if (jr.winner === "con") entry.con += 1;
    else entry.tie += 1;
    biasCounts.set(key, entry);
  }

  const judgeBias: JudgeBiasRow[] = Array.from(biasCounts.entries()).map(
    ([key, counts]) => {
      const [judge_id, topic_id] = key.split("|||");
      const samples = counts.pro + counts.con + counts.tie;
      const pro_rate = samples
        ? (counts.pro + 0.5 * counts.tie) / samples
        : 0;
      const con_rate = samples
        ? (counts.con + 0.5 * counts.tie) / samples
        : 0;
      const bias = pro_rate - con_rate;
      return {
        judge_id,
        category: counts.category,
        topic_id,
        pro_wins: counts.pro,
        con_wins: counts.con,
        ties: counts.tie,
        samples,
        pro_rate,
        con_rate,
        bias,
        adj_bias_mean: bias,
      };
    },
  );

  judgeBias.sort((a, b) => {
    const mag = Math.abs(b.bias) - Math.abs(a.bias);
    if (mag !== 0) return mag;
    return b.samples - a.samples;
  });

  return { judgeAgreement, judgeBias };
}

export function buildHighlightSpecs(
  highlightDerived?: DerivedData,
  fullDerived?: DerivedData,
  topN: number = 6,
  selectedCategories: string[] = [],
  pricing: PricingSnapshot,
  pricePerfMetric: PricePerfMetric,
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
      if (typeof m.cost_samples === "number") hintParts.push(`${m.cost_samples} turns`);
      return {
        label: m.model_id,
        value: perMillion,
        hint: hintParts.join(" • "),
      };
    })
    .sort((a, b) => a.value - b.value)
    .slice(0, topN)

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
