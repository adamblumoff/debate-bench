import { DerivedData } from "@/lib/types";
import { DatasetKey, DataRow } from "@/lib/server/chartSpec";

export function parseCompareParam(raw: string | string[] | undefined): string[] {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw.flatMap((v) => v.split(",")).filter(Boolean);
  return raw.split(",").filter(Boolean);
}

export function chooseModels(derived: DerivedData, requested: string[]): string[] {
  const valid = requested.filter((m) => derived.models.includes(m));
  if (valid.length) return Array.from(new Set(valid));
  return derived.modelStats.slice(0, 6).map((m) => m.model_id);
}

export function filterRowsByModels(derived: DerivedData, models: string[], dataset: DatasetKey): DataRow[] {
  const set = new Set(models);
  if (dataset === "debates") {
    return derived.debateRows.filter(
      (r) => set.has(r.pro_model_id as string) && set.has(r.con_model_id as string)
    );
  }
  return derived.judgeRows.filter(
    (r) => set.has(r.pro_model_id as string) && set.has(r.con_model_id as string)
  );
}
