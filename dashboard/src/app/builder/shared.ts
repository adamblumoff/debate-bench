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
  return derived.judgeRows.filter(
    (r) =>
      set.has(r.pro_model_id as string) && set.has(r.con_model_id as string),
  );
}
