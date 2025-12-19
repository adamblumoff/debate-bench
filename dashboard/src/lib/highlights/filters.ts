import { DerivedData, ModelStats } from "@/lib/types";

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
    const merged = mergeDerivedByCategories(
      derived,
      derivedByCategory,
      selectedCategories,
    );
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
      cur.mean_total_tokens = wAvg(cur.mean_total_tokens, s.mean_total_tokens);
      cur.win_rate = totalGames
        ? (cur.wins + 0.5 * cur.ties) / totalGames
        : cur.win_rate;
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
  const h2hMap = new Map<
    string,
    { row: string; col: string; win: number; samples: number }
  >();
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
    topicWinrates: derived.topicWinrates.filter((t) => allowed.has(t.model_id)),
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
