import { DebateRecord, CostSummary } from "@/lib/types";

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0;
  const clamped = Math.max(0, Math.min(1, q));
  const idx = Math.floor(clamped * (sorted.length - 1));
  return sorted[idx] ?? 0;
}

function normalizeCurrency(v: unknown): "USD" | "mixed" {
  if (typeof v !== "string") return "USD";
  const upper = v.toUpperCase();
  if (upper === "USD") return "USD";
  return "mixed";
}

export function computeCostSummary(
  debates: DebateRecord[],
  limit: number = 0,
): CostSummary {
  const n = Math.max(0, Math.floor(limit));
  const slice = n > 0 ? debates.slice(-n) : debates;

  const perDebateTotals: number[] = [];
  const debateRows: CostSummary["debates"] = [];

  const debaterCostByModel = new Map<string, { cost: number; tokens: number }>();
  const judgeCostByModel = new Map<string, { cost: number; tokens: number }>();
  const stageAgg = new Map<string, { cost: number; tokens: number }>();

  let currency: "USD" | "mixed" = "USD";

  let totalDebaterCost = 0;
  let totalJudgeCost = 0;

  slice.forEach((d, i) => {
    const transcript = d.transcript;
    const pro = transcript.pro_model_id;
    const con = transcript.con_model_id;

    let debaterCost = 0;
    let debaterTokens = 0;

    for (const turn of transcript.turns || []) {
      const speaker = turn.speaker;
      const modelId = speaker === "pro" ? pro : con;
      const prompt = typeof turn.prompt_tokens === "number" ? turn.prompt_tokens : 0;
      const completion =
        typeof turn.completion_tokens === "number" ? turn.completion_tokens : 0;
      const tokens = prompt + completion;
      debaterTokens += tokens;

      const stage = (turn.stage || "unknown").trim() || "unknown";
      const stageEntry = stageAgg.get(stage) || { cost: 0, tokens: 0 };
      stageEntry.tokens += tokens;
      stageAgg.set(stage, stageEntry);

      const modelEntry =
        debaterCostByModel.get(modelId) || { cost: 0, tokens: 0 };
      modelEntry.tokens += tokens;
      debaterCostByModel.set(modelId, modelEntry);

      const cost = typeof turn.cost === "number" ? turn.cost : 0;
      if (cost) {
        debaterCost += cost;
        modelEntry.cost += cost;
        debaterCostByModel.set(modelId, modelEntry);
        stageEntry.cost += cost;
        stageAgg.set(stage, stageEntry);
      }

      const cur = normalizeCurrency(turn.currency);
      if (cur !== currency) currency = "mixed";
    }

    let judgeCost = 0;
    let judgeTokens = 0;
    for (const j of d.judges || []) {
      const prompt = typeof j.prompt_tokens === "number" ? j.prompt_tokens : 0;
      const completion =
        typeof j.completion_tokens === "number" ? j.completion_tokens : 0;
      const tokens = prompt + completion;
      judgeTokens += tokens;

      const id = j.judge_id;
      const judgeEntry = judgeCostByModel.get(id) || { cost: 0, tokens: 0 };
      judgeEntry.tokens += tokens;
      judgeCostByModel.set(id, judgeEntry);

      const cost = typeof j.cost === "number" ? j.cost : 0;
      if (cost) {
        judgeCost += cost;
        judgeEntry.cost += cost;
        judgeCostByModel.set(id, judgeEntry);
      }

      const cur = normalizeCurrency(j.currency);
      if (cur !== currency) currency = "mixed";
    }

    totalDebaterCost += debaterCost;
    totalJudgeCost += judgeCost;
    const total = debaterCost + judgeCost;
    perDebateTotals.push(total);

    const createdAt =
      typeof d.created_at === "string"
        ? d.created_at
        : typeof (transcript as unknown as Record<string, unknown>).created_at ===
            "string"
          ? String((transcript as unknown as Record<string, unknown>).created_at)
          : undefined;

    debateRows.push({
      seq: i + 1,
      debate_id: transcript.debate_id,
      topic_id: transcript.topic.id,
      category: transcript.topic.category,
      motion: transcript.topic.motion,
      pro_model_id: pro,
      con_model_id: con,
      debater_cost_usd: debaterCost,
      judge_cost_usd: judgeCost,
      total_cost_usd: total,
      debater_tokens: debaterTokens,
      judge_tokens: judgeTokens,
      created_at: createdAt,
    });
  });

  const sortedTotals = [...perDebateTotals].sort((a, b) => a - b);
  const mean =
    perDebateTotals.length > 0
      ? perDebateTotals.reduce((acc, v) => acc + v, 0) / perDebateTotals.length
      : 0;
  const median = quantile(sortedTotals, 0.5);
  const p90 = quantile(sortedTotals, 0.9);

  const modelsMap = new Map<
    string,
    { debaterCost: number; judgeCost: number; tokens: number }
  >();
  for (const [id, v] of debaterCostByModel.entries()) {
    const cur = modelsMap.get(id) || { debaterCost: 0, judgeCost: 0, tokens: 0 };
    cur.debaterCost += v.cost;
    cur.tokens += v.tokens;
    modelsMap.set(id, cur);
  }
  for (const [id, v] of judgeCostByModel.entries()) {
    const cur = modelsMap.get(id) || { debaterCost: 0, judgeCost: 0, tokens: 0 };
    cur.judgeCost += v.cost;
    cur.tokens += v.tokens;
    modelsMap.set(id, cur);
  }

  const models = Array.from(modelsMap.entries())
    .map(([model_id, v]) => {
      const total = v.debaterCost + v.judgeCost;
      const usd_per_million_tokens =
        v.tokens > 0 ? (total / v.tokens) * 1_000_000 : undefined;
      return {
        model_id,
        debater_cost_usd: v.debaterCost,
        judge_cost_usd: v.judgeCost,
        total_cost_usd: total,
        total_tokens: v.tokens,
        usd_per_million_tokens,
      };
    })
    .sort((a, b) => b.total_cost_usd - a.total_cost_usd);

  const stages = Array.from(stageAgg.entries())
    .map(([stage, v]) => ({
      stage,
      cost_usd: v.cost,
      tokens: v.tokens,
    }))
    .sort((a, b) => b.cost_usd - a.cost_usd);

  return {
    debateCount: slice.length,
    currency,
    totals: {
      debater_cost_usd: totalDebaterCost,
      judge_cost_usd: totalJudgeCost,
      total_cost_usd: totalDebaterCost + totalJudgeCost,
    },
    per_debate: {
      mean_cost_usd: mean,
      median_cost_usd: median,
      p90_cost_usd: p90,
    },
    debates: debateRows,
    models,
    stages,
  };
}
