import { DerivedData } from "@/lib/types";
import { VisualizationSpec } from "vega-embed";
import { divergingRange, heatRange } from "@/lib/vegaTheme";

export function buildSideBiasSpec(
  derived: DerivedData,
  limit: number,
): VisualizationSpec {
  const side = derived.modelStats.map((m) => ({
    model: m.model_id,
    gap: m.pro_win_rate - m.con_win_rate,
    pro: m.pro_win_rate,
    con: m.con_win_rate,
  }));
  side.sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap));
  return {
    width: "container",
    height: 320,
    data: { values: side.slice(0, limit + 2) },
    mark: { type: "bar" },
    encoding: {
      x: {
        field: "gap",
        type: "quantitative",
        axis: { format: ".0%", title: "Pro – con win rate" },
        scale: { zero: true },
      },
      y: { field: "model", type: "nominal", sort: "-x" },
      color: {
        field: "gap",
        type: "quantitative",
        scale: { range: divergingRange },
      },
      tooltip: [
        { field: "model", title: "Model" },
        { field: "gap", title: "Gap", format: ".1%" },
        { field: "pro", title: "Pro win", format: ".1%" },
        { field: "con", title: "Con win", format: ".1%" },
      ],
    },
  } satisfies VisualizationSpec;
}

export function buildJudgeSideBiasSpec(
  derived: DerivedData,
  minSamples: number = 1,
): VisualizationSpec {
  const filtered = derived.judgeBias.filter(
    (j) => j.samples >= minSamples && typeof j.adj_bias === "number",
  );

  // compute mean adjusted bias per topic for sorting
  const topicBias = new Map<string, { sum: number; n: number }>();
  for (const row of filtered) {
    const entry = topicBias.get(row.topic_id) || { sum: 0, n: 0 };
    const val = row.adj_bias as number;
    entry.sum += val;
    entry.n += 1;
    topicBias.set(row.topic_id, entry);
  }
  const topicOrder = Array.from(topicBias.entries())
    .map(([topic_id, { sum, n }]) => ({ topic_id, avg: n ? sum / n : 0 }))
    .sort((a, b) => a.avg - b.avg) // most con-bias (negative) to most pro-bias (positive)
    .map((t) => t.topic_id);

  const values = filtered.map((j) => ({
    judge: j.judge_id,
    topic_id: j.topic_id,
    topic_motion: j.topic_motion,
    adj_bias: j.adj_bias as number,
    pro: j.pro_rate,
    con: j.con_rate,
    samples: j.samples,
    topic_avg_bias: (() => {
      const entry = topicBias.get(j.topic_id);
      if (!entry || !entry.n) return undefined;
      return entry.sum / entry.n;
    })(),
  }));

  return {
    width: { step: 90 },
    height: { step: 34 },
    data: { values },
    mark: { type: "rect" },
    encoding: {
      x: {
        field: "topic_id",
        type: "nominal",
        sort: topicOrder,
        axis: {
          labelAngle: -40,
          title: "Topic id",
          labelLimit: 90,
          labelPadding: 6,
        },
      },
      y: {
        field: "judge",
        type: "nominal",
        sort: "-x",
        axis: {
          title: "Judge model",
          titlePadding: 14,
          labelPadding: 10,
        },
      },
      color: {
        field: "adj_bias",
        type: "quantitative",
        scale: { domain: [-1, 0, 1], range: divergingRange },
        legend: { format: ".2f", title: "Pro – con bias" },
      },
      tooltip: [
        { field: "judge", title: "Judge" },
        { field: "topic_id", title: "Topic" },
        { field: "topic_motion", title: "Motion" },
        {
          field: "topic_avg_bias",
          title: "Avg bias (topic)",
          format: ".3f",
        },
        { field: "adj_bias", title: "Adj bias", format: ".3f" },
        { field: "pro", title: "Pro pick", format: ".3f" },
        { field: "con", title: "Con pick", format: ".3f" },
        { field: "samples", title: "Decisions" },
      ],
    },
    config: { axis: { labelLimit: 120 } },
  } satisfies VisualizationSpec;
}

export function buildJudgeSideBiasCvSpec(
  derived: DerivedData,
  minSamples: number = 1,
  stableOnly = false,
): VisualizationSpec {
  const filtered = derived.judgeBias.filter((j) => {
    if (j.samples < minSamples) return false;
    if (typeof j.adj_bias_mean !== "number") return false;
    if (stableOnly && j.stability !== "high") return false;
    return true;
  });

  const topicBias = new Map<string, { sum: number; n: number }>();
  for (const row of filtered) {
    const entry = topicBias.get(row.topic_id) || { sum: 0, n: 0 };
    entry.sum += row.adj_bias_mean as number;
    entry.n += 1;
    topicBias.set(row.topic_id, entry);
  }
  const topicOrder = Array.from(topicBias.entries())
    .map(([topic_id, { sum, n }]) => ({ topic_id, avg: n ? sum / n : 0 }))
    .sort((a, b) => a.avg - b.avg)
    .map((t) => t.topic_id);

  const values = filtered.map((j) => ({
    judge: j.judge_id,
    topic_id: j.topic_id,
    topic_motion: j.topic_motion,
    adj_bias_mean: j.adj_bias_mean as number,
    adj_bias_std: j.adj_bias_std,
    adj_bias_ci_low: j.adj_bias_ci_low,
    adj_bias_ci_high: j.adj_bias_ci_high,
    stability: j.stability,
    pro: j.pro_rate,
    con: j.con_rate,
    samples: j.samples,
    topic_avg_bias: (() => {
      const entry = topicBias.get(j.topic_id);
      if (!entry || !entry.n) return undefined;
      return entry.sum / entry.n;
    })(),
  }));

  return {
    width: { step: 90 },
    height: { step: 34 },
    data: { values },
    mark: { type: "rect" },
    encoding: {
      x: {
        field: "topic_id",
        type: "nominal",
        sort: topicOrder,
        axis: {
          labelAngle: -40,
          title: "Topic id",
          labelLimit: 90,
          labelPadding: 6,
        },
      },
      y: {
        field: "judge",
        type: "nominal",
        sort: "-x",
        axis: {
          title: "Judge model",
          titlePadding: 14,
          labelPadding: 10,
        },
      },
      color: {
        field: "adj_bias_mean",
        type: "quantitative",
        scale: { domain: [-1, 0, 1], range: divergingRange },
        legend: { format: ".2f", title: "Pro – con bias (CV mean)" },
      },
      tooltip: [
        { field: "judge", title: "Judge" },
        { field: "topic_id", title: "Topic" },
        { field: "topic_motion", title: "Motion" },
        {
          field: "topic_avg_bias",
          title: "Avg bias (topic)",
          format: ".3f",
        },
        { field: "adj_bias_mean", title: "Adj bias (mean)", format: ".3f" },
        { field: "adj_bias_ci_low", title: "CI low", format: ".3f" },
        { field: "adj_bias_ci_high", title: "CI high", format: ".3f" },
        { field: "stability", title: "Stability" },
        { field: "pro", title: "Pro pick", format: ".3f" },
        { field: "con", title: "Con pick", format: ".3f" },
        { field: "samples", title: "Decisions" },
      ],
    },
    config: { axis: { labelLimit: 120 } },
  } satisfies VisualizationSpec;
}

export function buildH2HSpec(derived: DerivedData): VisualizationSpec {
  return {
    width: "container",
    height: 380,
    data: { values: derived.headToHead },
    mark: { type: "rect" },
    encoding: {
      x: { field: "col", type: "nominal" },
      y: { field: "row", type: "nominal" },
      color: {
        field: "win_rate",
        type: "quantitative",
        scale: { range: heatRange, domain: [0, 1] },
        legend: {
          format: ".0%",
          labelOverlap: true,
          values: [0, 0.2, 0.4, 0.6, 0.8, 1],
          gradientLength: 140,
        },
      },
      tooltip: [
        { field: "row", type: "nominal", title: "row" },
        { field: "col", type: "nominal", title: "col" },
        {
          field: "win_rate",
          type: "quantitative",
          title: "win %",
          format: ".1%",
        },
        { field: "samples", type: "quantitative", title: "n" },
      ],
    },
    config: { axis: { labelAngle: -45 } },
  } satisfies VisualizationSpec;
}

export function buildJudgeHeatSpec(derived: DerivedData): VisualizationSpec {
  return {
    width: "container",
    height: 260,
    data: { values: derived.judgeAgreement },
    mark: { type: "rect" },
    encoding: {
      x: { field: "judge_a", type: "nominal" },
      y: { field: "judge_b", type: "nominal" },
      color: {
        field: "agreement_rate",
        type: "quantitative",
        scale: { range: heatRange, domain: [0, 1] },
        legend: {
          format: ".0%",
          values: [0, 0.2, 0.4, 0.6, 0.8, 1],
          gradientLength: 140,
          labelOverlap: true,
        },
      },
      tooltip: [
        { field: "judge_a", type: "nominal" },
        { field: "judge_b", type: "nominal" },
        { field: "agreement_rate", type: "quantitative", format: ".1%" },
        { field: "samples", type: "quantitative" },
      ],
    },
    config: { axis: { labelAngle: -30 } },
  } satisfies VisualizationSpec;
}

export function buildCategoryHeatSpec(
  derived: DerivedData,
  category: string,
): VisualizationSpec {
  const rows = derived.topicWinrates
    .filter((t) => category === "all" || t.category === category)
    .map((t) => ({
      category: t.category || t.topic_id,
      model: t.model_id,
      win_rate: t.win_rate,
      wins: t.wins,
      samples: t.samples,
    }));
  return {
    width: "container",
    height: 380,
    data: { values: rows },
    mark: { type: "rect" },
    encoding: {
      x: { field: "category", type: "nominal", sort: "-y" },
      y: { field: "model", type: "nominal" },
      color: {
        field: "win_rate",
        type: "quantitative",
        scale: { range: heatRange, domain: [0, 1] },
        legend: {
          format: ".0%",
          labelOverlap: true,
          values: [0, 0.2, 0.4, 0.6, 0.8, 1],
          gradientLength: 140,
        },
      },
      tooltip: [
        { field: "model", type: "nominal" },
        { field: "category", type: "nominal" },
        { field: "win_rate", type: "quantitative", format: ".1%" },
        { field: "wins", type: "quantitative" },
        { field: "samples", type: "quantitative" },
      ],
    },
    config: { axis: { labelAngle: -40 } },
  } satisfies VisualizationSpec;
}
