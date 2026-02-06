import { toPercent } from "@/lib/format";
import { DerivedData } from "@/lib/types";
import { Kpi } from "./types";

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
