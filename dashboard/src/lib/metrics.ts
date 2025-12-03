import { DebateRecord, DerivedData, HeadToHeadCell, JudgeAgreementRow, JudgeRowForBuilder, ModelStats, TopicWinrate, DebateRowForBuilder, Winner } from "./types";

export function buildDerived(debates: DebateRecord[]): DerivedData {
  if (!debates.length) {
    return {
      models: [],
      dimensions: [],
      modelStats: [],
      headToHead: [],
      topicWinrates: [],
      judgeAgreement: [],
      debateRows: [],
      judgeRows: [],
    };
  }

  const dimensions = Object.keys(debates[0].aggregate.mean_pro || {});

  const models = Array.from(
    new Set(
      debates.flatMap((d) => [d.transcript.pro_model_id, d.transcript.con_model_id])
    )
  ).sort();

  const statsMap = new Map<string, ModelStats>();
  const ratings = new Map<string, number>();
  const tokenAgg = new Map<
    string,
    { prompt: number; completion: number; promptTurns: number; completionTurns: number }
  >();
  const headWin = new Map<string, number>();
  const headTot = new Map<string, number>();
  const topicStats = new Map<string, TopicWinrate>();
  const judgeAgreementPairs = new Map<string, { agree: number; total: number }>();
  const judgeRows: JudgeRowForBuilder[] = [];
  const debateRows: DebateRowForBuilder[] = [];

  const ensureStats = (id: string) => {
    if (!statsMap.has(id)) {
      statsMap.set(id, {
        model_id: id,
        rating: 1500,
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
    if (!ratings.has(id)) ratings.set(id, 1500);
    return ratings.get(id)!;
  };

  const ensureTokens = (id: string) => {
    if (!tokenAgg.has(id)) tokenAgg.set(id, { prompt: 0, completion: 0, promptTurns: 0, completionTurns: 0 });
    return tokenAgg.get(id)!;
  };

  const hkey = (a: string, b: string) => `${a}|||${b}`;

  const kFactor = 24;

  for (const d of debates) {
    const { pro_model_id: pro, con_model_id: con, topic } = d.transcript;
    const winner = d.aggregate.winner;

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
    if (winner === "con") headWin.set(hkey(con, pro), (headWin.get(hkey(con, pro)) ?? 0) + 1);
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

    // judge rows and agreement
    const winnersByJudge: Record<string, Winner> = {};
    for (const j of d.judges) {
      judgeRows.push({
        judge_id: j.judge_id,
        winner: j.winner,
        pro_model_id: pro,
        con_model_id: con,
        topic_id: topic.id,
        category: topic.category,
      });
      winnersByJudge[j.judge_id] = j.winner;
    }
    const judgeIds = Object.keys(winnersByJudge);
    for (let i = 0; i < judgeIds.length; i++) {
      for (let k = i + 1; k < judgeIds.length; k++) {
        const a = judgeIds[i];
        const b = judgeIds[k];
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
      s.mean_completion_tokens = t.completionTurns ? t.completion / t.completionTurns : 0;
      s.mean_total_tokens = s.mean_prompt_tokens + s.mean_completion_tokens;
    }
  });

  const modelStats = Array.from(statsMap.values()).sort((a, b) => b.rating - a.rating);

  const headToHead: HeadToHeadCell[] = [];
  for (const m of models) {
    for (const o of models) {
      if (m === o) continue;
      const tot = headTot.get(hkey(m, o)) || 0;
      const win = headWin.get(hkey(m, o)) || 0;
      headToHead.push({ row: m, col: o, win_rate: tot ? win / tot : 0, samples: tot });
    }
  }

  const topicWinrates = Array.from(topicStats.values()).map((t) => ({
    ...t,
    win_rate: (t.wins + 0.5 * t.ties) / (t.samples || 1),
  }));

  const judgeAgreement: JudgeAgreementRow[] = Array.from(judgeAgreementPairs.entries()).map(
    ([key, val]) => {
      const [a, b] = key.split("|||");
      return {
        judge_a: a,
        judge_b: b,
        agreement_rate: val.total ? val.agree / val.total : 0,
        samples: val.total,
      };
    }
  );

  return {
    models,
    dimensions,
    modelStats,
    headToHead,
    topicWinrates,
    judgeAgreement,
    debateRows,
    judgeRows,
  };
}
