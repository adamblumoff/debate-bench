import {
  DebateRecord,
  DerivedData,
  HeadToHeadCell,
  JudgeAgreementRow,
  JudgeBiasRow,
  JudgeRowForBuilder,
  ModelStats,
  TopicWinrate,
  DebateRowForBuilder,
  Winner,
} from "../types";
import { fitLogisticRidge, hashFold, sigmoid, SparseExample } from "./logistic";

type BiasRow = {
  judge_id: string;
  winner: Winner;
  pro_model_id: string;
  con_model_id: string;
  topic_id: string;
  debate_id?: string;
};

type BuildDerivedOptions = {
  includeRows?: boolean;
  includeBiasCv?: boolean;
};

const LAMBDA = {
  judge: 0.5,
  topic: 0.5,
  model: 0.5,
  topic_model: 0.5,
};

export function buildDerived(
  debates: DebateRecord[],
  opts: BuildDerivedOptions = {},
): DerivedData {
  if (!debates.length) {
    return {
      models: [],
      dimensions: [],
      modelStats: [],
      headToHead: [],
      topicWinrates: [],
      judgeAgreement: [],
      judgeBias: [],
      debateRows: [],
      judgeRows: [],
    };
  }

  // Union all score dimensions to avoid depending on the first record's shape.
  const dimSet = new Set<string>();
  for (const d of debates) {
    Object.keys(d.aggregate.mean_pro || {}).forEach((k) => dimSet.add(k));
    Object.keys(d.aggregate.mean_con || {}).forEach((k) => dimSet.add(k));
  }
  const dimensions = Array.from(dimSet).sort();

  const models = Array.from(
    new Set(
      debates.flatMap((d) => [
        d.transcript.pro_model_id,
        d.transcript.con_model_id,
      ]),
    ),
  ).sort();

  // Deterministic ordering: created_at if present, then debate_id, then original index.
  const withIndex = debates.map((d, idx) => ({ d, idx }));
  const parseTs = (v?: string) => {
    const t = v ? Date.parse(v) : NaN;
    return Number.isFinite(t) ? t : NaN;
  };
  withIndex.sort((a, b) => {
    const ta = parseTs(a.d.created_at);
    const tb = parseTs(b.d.created_at);
    if (!Number.isNaN(ta) && !Number.isNaN(tb) && ta !== tb) return ta - tb;
    if (!Number.isNaN(ta) && Number.isNaN(tb)) return -1;
    if (Number.isNaN(ta) && !Number.isNaN(tb)) return 1;
    const ida = a.d.transcript.debate_id || "";
    const idb = b.d.transcript.debate_id || "";
    if (ida !== idb) return ida < idb ? -1 : 1;
    return a.idx - b.idx;
  });

  const defaultInitial = 400;
  const defaultK = 32;
  const eloInitial =
    typeof debates[0]?.elo?.initial_rating === "number"
      ? debates[0].elo!.initial_rating
      : defaultInitial;
  const kFactor =
    typeof debates[0]?.elo?.k_factor === "number"
      ? debates[0].elo!.k_factor
      : defaultK;

  const statsMap = new Map<string, ModelStats>();
  const ratings = new Map<string, number>();
  const tokenAgg = new Map<
    string,
    {
      prompt: number;
      completion: number;
      promptTurns: number;
      completionTurns: number;
    }
  >();
  const costAgg = new Map<
    string,
    {
      cost: number;
      samples: number;
    }
  >();
  const headWin = new Map<string, number>();
  const headTot = new Map<string, number>();
  const topicStats = new Map<string, TopicWinrate>();
  const judgeAgreementPairs = new Map<
    string,
    { agree: number; total: number }
  >();
  const judgeBiasCounts = new Map<
    string,
    {
      pro: number;
      con: number;
      tie: number;
      category: string;
      topic_id: string;
      topic_motion?: string;
    }
  >();
  const includeRows = opts.includeRows !== false;
  const includeBiasCv = opts.includeBiasCv === true;
  const judgeRows: JudgeRowForBuilder[] = [];
  const debateRows: DebateRowForBuilder[] = [];
  const biasRows: BiasRow[] = [];
  const judgeIds: string[] = [];
  const topicIds: string[] = [];
  const seenJudge = new Set<string>();
  const seenTopic = new Set<string>();

  const ensureStats = (id: string) => {
    if (!statsMap.has(id)) {
      statsMap.set(id, {
        model_id: id,
        rating: eloInitial,
        wins: 0,
        losses: 0,
        ties: 0,
        games: 0,
        win_rate: 0,
        pro_games: 0,
        con_games: 0,
        pro_win_rate: 0,
        con_win_rate: 0,
        mean_prompt_tokens: 0,
        mean_completion_tokens: 0,
        mean_total_tokens: 0,
      });
    }
    return statsMap.get(id)!;
  };

  const ensureRating = (id: string) => {
    if (!ratings.has(id)) ratings.set(id, eloInitial);
    return ratings.get(id)!;
  };

  const ensureTokens = (id: string) => {
    if (!tokenAgg.has(id))
      tokenAgg.set(id, {
        prompt: 0,
        completion: 0,
        promptTurns: 0,
        completionTurns: 0,
      });
    return tokenAgg.get(id)!;
  };

  const ensureCost = (id: string) => {
    if (!costAgg.has(id)) costAgg.set(id, { cost: 0, samples: 0 });
    return costAgg.get(id)!;
  };

  const hkey = (a: string, b: string) => `${a}|||${b}`;

  for (const { d } of withIndex) {
    const { pro_model_id: pro, con_model_id: con, topic } = d.transcript;
    const category = topic.category || "uncategorized";
    const winner = d.aggregate.winner;

    if (!seenTopic.has(topic.id)) {
      topicIds.push(topic.id);
      seenTopic.add(topic.id);
    }

    const proStats = ensureStats(pro);
    const conStats = ensureStats(con);
    proStats.games += 1;
    conStats.games += 1;
    proStats.pro_games += 1;
    conStats.con_games += 1;

    // Elo update
    const proRating = ensureRating(pro);
    const conRating = ensureRating(con);
    const expectedPro = 1 / (1 + Math.pow(10, (conRating - proRating) / 400));
    const scorePro = winner === "pro" ? 1 : winner === "con" ? 0 : 0.5;
    const scoreCon = 1 - scorePro;
    ratings.set(pro, proRating + kFactor * (scorePro - expectedPro));
    ratings.set(con, conRating + kFactor * (scoreCon - (1 - expectedPro)));

    if (winner === "pro") {
      proStats.wins += 1;
      conStats.losses += 1;
      proStats.pro_win_rate += 1;
    } else if (winner === "con") {
      conStats.wins += 1;
      proStats.losses += 1;
      conStats.con_win_rate += 1;
    } else {
      proStats.ties += 1;
      conStats.ties += 1;
      proStats.pro_win_rate += 0.5;
      conStats.con_win_rate += 0.5;
    }

    const hk = hkey(pro, con);
    const hkRev = hkey(con, pro);
    headTot.set(hk, (headTot.get(hk) ?? 0) + 1);
    headTot.set(hkRev, (headTot.get(hkRev) ?? 0) + 1);
    if (winner === "pro") headWin.set(hk, (headWin.get(hk) ?? 0) + 1);
    if (winner === "con")
      headWin.set(hkey(con, pro), (headWin.get(hkey(con, pro)) ?? 0) + 1);
    if (winner === "tie") {
      headWin.set(hk, (headWin.get(hk) ?? 0) + 0.5);
      headWin.set(hkey(con, pro), (headWin.get(hkey(con, pro)) ?? 0) + 0.5);
    }

    const tkey = `${topic.id}|||${topic.category || ""}|||${pro}`;
    const ckey = `${topic.id}|||${topic.category || ""}|||${con}`;
    const ensureTopic = (key: string, model: string) => {
      if (!topicStats.has(key)) {
        const [tid, cat] = key.split("|||");
        topicStats.set(key, {
          topic_id: tid,
          category: cat || undefined,
          model_id: model,
          wins: 0,
          losses: 0,
          ties: 0,
          win_rate: 0,
          samples: 0,
        });
      }
      return topicStats.get(key)!;
    };
    const pTopic = ensureTopic(tkey, pro);
    const cTopic = ensureTopic(ckey, con);
    if (winner === "pro") {
      pTopic.wins += 1;
      cTopic.losses += 1;
    } else if (winner === "con") {
      cTopic.wins += 1;
      pTopic.losses += 1;
    } else {
      pTopic.ties += 1;
      cTopic.ties += 1;
    }
    pTopic.samples += 1;
    cTopic.samples += 1;

    // debate rows for builder
    if (includeRows) {
      const row: DebateRowForBuilder = {
        pro_model_id: pro,
        con_model_id: con,
        winner,
        topic_id: topic.id,
        category: topic.category,
      };
      for (const dim of dimensions) {
        row[`mean_pro_${dim}`] = d.aggregate.mean_pro[dim];
        row[`mean_con_${dim}`] = d.aggregate.mean_con[dim];
        row[`gap_${dim}`] =
          (d.aggregate.mean_pro[dim] ?? 0) - (d.aggregate.mean_con[dim] ?? 0);
      }
      debateRows.push(row);
    }

    // judge rows and agreement
    const winnersByJudge: Record<string, Winner> = {};
    for (const j of d.judges) {
      if (!seenJudge.has(j.judge_id)) {
        judgeIds.push(j.judge_id);
        seenJudge.add(j.judge_id);
      }
      const sideScore = j.winner === "pro" ? 1 : j.winner === "con" ? -1 : 0;
      const biasKey = `${j.judge_id}|||${topic.id}`;
      const biasCounts = judgeBiasCounts.get(biasKey) || {
        pro: 0,
        con: 0,
        tie: 0,
        category,
        topic_id: topic.id,
        topic_motion: topic.motion,
      };
      if (j.winner === "pro") biasCounts.pro += 1;
      else if (j.winner === "con") biasCounts.con += 1;
      else biasCounts.tie += 1;
      judgeBiasCounts.set(biasKey, biasCounts);

      biasRows.push({
        judge_id: j.judge_id,
        winner: j.winner,
        pro_model_id: pro,
        con_model_id: con,
        topic_id: topic.id,
        debate_id: d.transcript.debate_id,
      });
      if (includeRows) {
        judgeRows.push({
          judge_id: j.judge_id,
          winner: j.winner,
          pro_model_id: pro,
          con_model_id: con,
          topic_id: topic.id,
          category: topic.category,
          side_score: sideScore,
          pro_pick: j.winner === "pro" ? 1 : 0,
          con_pick: j.winner === "con" ? 1 : 0,
          tie_pick: j.winner === "tie" || j.winner === null ? 1 : 0,
          debate_id: d.transcript.debate_id,
        });
      }
      winnersByJudge[j.judge_id] = j.winner;
    }
    const panelJudgeIds = Object.keys(winnersByJudge);
    for (let i = 0; i < panelJudgeIds.length; i++) {
      for (let k = i + 1; k < panelJudgeIds.length; k++) {
        const a = panelJudgeIds[i];
        const b = panelJudgeIds[k];
        const key = hkey(a, b);
        const entry = judgeAgreementPairs.get(key) || { agree: 0, total: 0 };
        entry.total += 1;
        if (winnersByJudge[a] === winnersByJudge[b]) entry.agree += 1;
        judgeAgreementPairs.set(key, entry);
      }
    }

    // token accumulation per turn
    for (const turn of d.transcript.turns) {
      const modelId = turn.speaker === "pro" ? pro : con;
      const agg = ensureTokens(modelId);
      if (typeof turn.prompt_tokens === "number") {
        agg.prompt += turn.prompt_tokens;
        agg.promptTurns += 1;
      }
      if (typeof turn.completion_tokens === "number") {
        agg.completion += turn.completion_tokens;
        agg.completionTurns += 1;
      }
      if (typeof turn.cost === "number") {
        const c = ensureCost(modelId);
        c.cost += turn.cost;
        c.samples += 1;
      }
    }
  }

  // finalize stats
  statsMap.forEach((s) => {
    s.win_rate = (s.wins + 0.5 * s.ties) / (s.games || 1);
    s.pro_win_rate = s.pro_games ? s.pro_win_rate / s.pro_games : 0;
    s.con_win_rate = s.con_games ? s.con_win_rate / s.con_games : 0;
    s.rating = ratings.get(s.model_id) ?? 1500;
    const t = tokenAgg.get(s.model_id);
    if (t) {
      s.mean_prompt_tokens = t.promptTurns ? t.prompt / t.promptTurns : 0;
      s.mean_completion_tokens = t.completionTurns
        ? t.completion / t.completionTurns
        : 0;
      s.mean_total_tokens = s.mean_prompt_tokens + s.mean_completion_tokens;
    }
    const c = costAgg.get(s.model_id);
    if (c && c.samples) {
      s.mean_cost_usd = c.cost / c.samples;
      s.total_cost_usd = c.cost;
      s.cost_samples = c.samples;
    }
  });

  const modelStats = Array.from(statsMap.values()).sort(
    (a, b) => b.rating - a.rating,
  );

  const headToHead: HeadToHeadCell[] = [];
  for (const m of models) {
    for (const o of models) {
      if (m === o) continue;
      const tot = headTot.get(hkey(m, o)) || 0;
      const win = headWin.get(hkey(m, o)) || 0;
      headToHead.push({
        row: m,
        col: o,
        win_rate: tot ? win / tot : 0,
        samples: tot,
      });
    }
  }

  const topicWinrates = Array.from(topicStats.values()).map((t) => ({
    ...t,
    win_rate: (t.wins + 0.5 * t.ties) / (t.samples || 1),
  }));

  const judgeAgreement: JudgeAgreementRow[] = Array.from(
    judgeAgreementPairs.entries(),
  ).map(([key, val]) => {
    const [a, b] = key.split("|||");
    return {
      judge_a: a,
      judge_b: b,
      agreement_rate: val.total ? val.agree / val.total : 0,
      samples: val.total,
    };
  });

  const judgeBias: JudgeBiasRow[] = Array.from(judgeBiasCounts.entries()).map(
    ([key, counts]): JudgeBiasRow => {
      const [judge_id, topic_id] = key.split("|||");
      const samples = counts.pro + counts.con + counts.tie;
      const pro_rate = samples ? (counts.pro + 0.5 * counts.tie) / samples : 0;
      const con_rate = samples ? (counts.con + 0.5 * counts.tie) / samples : 0;
      return {
        judge_id,
        category: counts.category,
        topic_id,
        topic_motion: counts.topic_motion,
        pro_wins: counts.pro,
        con_wins: counts.con,
        ties: counts.tie,
        samples,
        pro_rate,
        con_rate,
        bias: pro_rate - con_rate,
        adj_bias: undefined,
        topic_avg_bias: undefined,
        topic_avg_adj_bias: undefined,
      };
    },
  );
  judgeBias.sort((a, b) => {
    const mag = Math.abs(b.bias) - Math.abs(a.bias);
    if (mag !== 0) return mag;
    return b.samples - a.samples;
  });

  // -------- Adjusted judge/topic bias via ridge logistic (controls for model strength) --------
  // Helper to build feature indices and examples (with topic x model interactions)
  const topicModelKeys = new Set<string>();
  for (const jr of biasRows) {
    if (jr.topic_id && jr.pro_model_id)
      topicModelKeys.add(`${jr.topic_id}|||${jr.pro_model_id}`);
    if (jr.topic_id && jr.con_model_id)
      topicModelKeys.add(`${jr.topic_id}|||${jr.con_model_id}`);
  }
  const topicModel = Array.from(topicModelKeys).sort();

  const judgeIndex = new Map<string, number>();
  judgeIds.forEach((j, i) => judgeIndex.set(j, i));
  const topicIndex = new Map<string, number>();
  topicIds.forEach((t, i) => topicIndex.set(t, i));
  const modelIndex = new Map<string, number>();
  models.forEach((m, i) => modelIndex.set(m, i));
  const topicModelIndex = new Map<string, number>();
  topicModel.forEach((tm, i) => topicModelIndex.set(tm, i));

  const offsetJudge = 1;
  const offsetTopic = offsetJudge + judgeIds.length;
  const offsetModel = offsetTopic + topicIds.length;
  const offsetTopicModel = offsetModel + models.length;
  const numFeatures = offsetTopicModel + topicModel.length;

  const penalties = new Float64Array(numFeatures);
  penalties.fill(LAMBDA.model, offsetModel, offsetTopicModel);
  penalties.fill(LAMBDA.topic, offsetTopic, offsetModel);
  penalties.fill(LAMBDA.judge, offsetJudge, offsetTopic);
  penalties.fill(LAMBDA.topic_model, offsetTopicModel, numFeatures);
  penalties[0] = LAMBDA.judge;

  const buildExamples = (holdoutFold: number | null, folds: number) => {
    const ex: SparseExample[] = [];
    for (const jr of biasRows) {
      if (jr.winner === null || jr.winner === "tie") continue;
      if (!jr.topic_id || !judgeIndex.has(jr.judge_id)) continue;
      const fold = hashFold(
        String(jr.debate_id ?? `${jr.topic_id}-${jr.judge_id}`),
        folds,
      );
      if (holdoutFold !== null && fold === holdoutFold) continue;
      const tIdx = topicIndex.get(jr.topic_id);
      if (tIdx === undefined) continue;
      const idx: number[] = [0];
      const val: number[] = [1];
      idx.push(offsetJudge + judgeIndex.get(jr.judge_id)!);
      val.push(1);
      idx.push(offsetTopic + tIdx);
      val.push(1);
      const pro = jr.pro_model_id as string;
      const con = jr.con_model_id as string;
      if (modelIndex.has(pro)) {
        idx.push(offsetModel + modelIndex.get(pro)!);
        val.push(1);
      }
      if (modelIndex.has(con)) {
        idx.push(offsetModel + modelIndex.get(con)!);
        val.push(-1);
      }
      if (jr.topic_id) {
        const proKey = `${jr.topic_id}|||${pro}`;
        const conKey = `${jr.topic_id}|||${con}`;
        if (topicModelIndex.has(proKey)) {
          idx.push(offsetTopicModel + topicModelIndex.get(proKey)!);
          val.push(1);
        }
        if (topicModelIndex.has(conKey)) {
          idx.push(offsetTopicModel + topicModelIndex.get(conKey)!);
          val.push(-1);
        }
      }
      ex.push({
        y: jr.winner === "pro" ? 1 : 0,
        idx,
        val,
        judge_id: jr.judge_id,
        topic_id: jr.topic_id as string,
      });
    }
    return ex;
  };

  const adjFor = (w: Float64Array, judge_id: string, topic_id: string) => {
    const jIdx = judgeIndex.get(judge_id);
    const tIdx = topicIndex.get(topic_id);
    if (jIdx === undefined || tIdx === undefined) return undefined;
    const logit = w[0] + w[offsetJudge + jIdx] + w[offsetTopic + tIdx];
    const p = sigmoid(logit);
    return 2 * p - 1;
  };

  if (judgeIds.length && topicIds.length && biasRows.length) {
    const examples = buildExamples(null, 1);
    if (examples.length && numFeatures > 1) {
      const w = fitLogisticRidge(examples, numFeatures, {
        lambda: 0.5,
        lr: 0.2,
        iters: 250,
        penalties,
      });

      const topicAdjStats = new Map<string, { sum: number; n: number }>();
      const topicRawStats = new Map<string, { sum: number; n: number }>();

      for (const jb of judgeBias) {
        const adj = adjFor(w, jb.judge_id, jb.topic_id);
        jb.adj_bias = adj;
        const rawEntry = topicRawStats.get(jb.topic_id) || { sum: 0, n: 0 };
        rawEntry.sum += jb.bias;
        rawEntry.n += 1;
        topicRawStats.set(jb.topic_id, rawEntry);

        const adjEntry = topicAdjStats.get(jb.topic_id) || { sum: 0, n: 0 };
        adjEntry.sum += adj ?? jb.bias;
        adjEntry.n += 1;
        topicAdjStats.set(jb.topic_id, adjEntry);
      }

      for (const jb of judgeBias) {
        const raw = topicRawStats.get(jb.topic_id);
        jb.topic_avg_bias = raw && raw.n ? raw.sum / raw.n : undefined;
        const adj = topicAdjStats.get(jb.topic_id);
        jb.topic_avg_adj_bias =
          adj && adj.n ? adj.sum / adj.n : jb.topic_avg_bias;
      }

      if (includeBiasCv) {
        // 5-fold CV for stability
        const folds = 5;
        const cvBias = new Map<string, number[]>();
        for (let f = 0; f < folds; f++) {
          const exFold = buildExamples(f, folds);
          if (!exFold.length) continue;
          const wf = fitLogisticRidge(exFold, numFeatures, {
            lambda: 0.5,
            lr: 0.2,
            iters: 220,
            penalties,
          });
          for (const jb of judgeBias) {
            const adj = adjFor(wf, jb.judge_id, jb.topic_id);
            if (typeof adj !== "number") continue;
            const key = `${jb.judge_id}|||${jb.topic_id}`;
            if (!cvBias.has(key)) cvBias.set(key, []);
            cvBias.get(key)!.push(adj);
          }
        }

        for (const jb of judgeBias) {
          const arr = cvBias.get(`${jb.judge_id}|||${jb.topic_id}`);
          if (!arr || !arr.length) continue;
          const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
          const variance =
            arr.length > 1
              ? arr.reduce((a, b) => a + (b - mean) ** 2, 0) /
                (arr.length - 1)
              : 0;
          const std = Math.sqrt(variance);
          const ciLow = mean - 1.96 * std;
          const ciHigh = mean + 1.96 * std;
          jb.adj_bias_mean = mean;
          jb.adj_bias_std = std;
          jb.adj_bias_ci_low = ciLow;
          jb.adj_bias_ci_high = ciHigh;
          jb.stability =
            arr.length >= 5 && (ciLow > 0 || ciHigh < 0)
              ? "high"
              : arr.length >= 3
                ? "med"
                : "low";
        }
      }
    }
  }

  return {
    models,
    dimensions,
    modelStats,
    headToHead,
    topicWinrates,
    judgeAgreement,
    judgeBias,
    debateRows: includeRows ? debateRows : [],
    judgeRows: includeRows ? judgeRows : [],
  };
}
