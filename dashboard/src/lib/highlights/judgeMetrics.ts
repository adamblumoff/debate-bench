import {
  JudgeAgreementRow,
  JudgeBiasRow,
  JudgeRowForBuilder,
  Winner,
} from "@/lib/types";

export function recomputeJudgeMetrics(judgeRows: JudgeRowForBuilder[]): {
  judgeAgreement: JudgeAgreementRow[];
  judgeBias: JudgeBiasRow[];
} {
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

  const judgeAgreement: JudgeAgreementRow[] = Array.from(agreePairs.entries())
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
    {
      pro: number;
      con: number;
      tie: number;
      category: string;
      topic_id: string;
    }
  >();
  for (const jr of judgeRows) {
    if (!jr.judge_id || !jr.topic_id) continue;
    const category = (jr.category as string) || "uncategorized";
    const key = `${jr.judge_id}|||${jr.topic_id}`;
    const entry = biasCounts.get(key) || {
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
      const pro_rate = samples ? (counts.pro + 0.5 * counts.tie) / samples : 0;
      const con_rate = samples ? (counts.con + 0.5 * counts.tie) / samples : 0;
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
