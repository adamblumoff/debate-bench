import { DerivedData } from "@/lib/types";
import { DatasetKey, DataRow } from "@/lib/server/chartSpec";
import { MIN_COMPARE, MAX_COMPARE } from "@/lib/compareLimits";

export function parseCompareParam(
  raw: string | string[] | undefined,
): string[] {
  if (!raw) return [];
  if (Array.isArray(raw))
    return raw.flatMap((v) => v.split(",")).filter(Boolean);
  return raw.split(",").filter(Boolean);
}

export function chooseModels(
  derived: DerivedData,
  requested: string[],
): string[] {
  const valid = requested.filter((m) => derived.models.includes(m));
  const unique = Array.from(new Set(valid)).slice(0, MAX_COMPARE);
  if (unique.length >= MIN_COMPARE) return unique;

  const fill = derived.modelStats
    .map((m) => m.model_id)
    .filter((m) => !unique.includes(m))
    .slice(0, MAX_COMPARE - unique.length);

  return [...unique, ...fill].slice(0, MAX_COMPARE);
}

export function filterRowsByModels(
  derived: DerivedData,
  models: string[],
  dataset: DatasetKey,
): DataRow[] {
  const set = new Set(models);
  if (dataset === "debates") {
    return derived.debateRows.filter(
      (r) =>
        set.has(r.pro_model_id as string) && set.has(r.con_model_id as string),
    );
  }
  if (dataset === "judges") {
    return derived.judgeRows.filter(
      (r) =>
        set.has(r.pro_model_id as string) && set.has(r.con_model_id as string),
    );
  }
  // judge_bias: re-aggregate limited to selected models
  const agg = new Map<
    string,
    { pro: number; con: number; tie: number; samples: number; motion?: string; category?: string }
  >();
  for (const row of derived.judgeRows) {
    if (
      !set.has(row.pro_model_id as string) ||
      !set.has(row.con_model_id as string)
    )
      continue;
    const key = `${row.judge_id}|||${row.topic_id}`;
    const entry =
      agg.get(key) ||
      {
        pro: 0,
        con: 0,
        tie: 0,
        samples: 0,
        motion: undefined,
        category: row.category,
      };
    if (row.winner === "pro") entry.pro += 1;
    else if (row.winner === "con") entry.con += 1;
    else entry.tie += 1;
    entry.samples += 1;
    if (!entry.motion && typeof row.topic_id === "string") {
      // motion text not present in judgeRows; leave undefined
    }
    agg.set(key, entry);
  }
  const rows: DataRow[] = Array.from(agg.entries()).map(([key, c]) => {
    const [judge_id, topic_id] = key.split("|||");
    const pro_rate = c.samples ? (c.pro + 0.5 * c.tie) / c.samples : 0;
    const con_rate = c.samples ? (c.con + 0.5 * c.tie) / c.samples : 0;
    return {
      judge_id,
      topic_id,
      topic_motion: c.motion,
      category: c.category,
      pro_wins: c.pro,
      con_wins: c.con,
      ties: c.tie,
      samples: c.samples,
      pro_rate,
      con_rate,
      bias: pro_rate - con_rate,
    } as DataRow;
  });
  rows.sort((a, b) => Math.abs((b.bias as number) ?? 0) - Math.abs((a.bias as number) ?? 0));
  return rows;
}
