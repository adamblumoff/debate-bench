import { VisualizationSpec } from "vega-embed";
import { Config } from "vega-lite";

const TEXT = "#1a1612";
const MUTED = "#8a7e72";
const BORDER = "#d4cdc2";

export const accentRange = [
  "#c83c2c",
  "#d06858",
  "#b8a08c",
  "#8a7e72",
  "#d4cdc2",
  "#e8c4b0",
];
export const heatRange = [
  "#f5f1eb",
  "#e8dfd2",
  "#d4c8b5",
  "#b8a08c",
  "#8a6e58",
  "#c83c2c",
];
export const divergingRange = [
  "#1a5f9e",
  "#6b9cc4",
  "#f5f1eb",
  "#d0886c",
  "#c83c2c",
  "#8b1a0e",
];

const baseConfig: Config = {
  background: "transparent",
  view: { stroke: "transparent", fill: "transparent" },
  axis: {
    labelColor: MUTED,
    titleColor: TEXT,
    gridColor: BORDER,
    gridOpacity: 0.14,
    tickColor: BORDER,
    domainColor: BORDER,
    labelFontSize: 11,
    titleFontSize: 12,
  },
  legend: {
    labelColor: TEXT,
    titleColor: TEXT,
    orient: "top",
    labelFontSize: 11,
    titleFontSize: 12,
    padding: 6,
  },
  header: { labelColor: TEXT, titleColor: TEXT },
  title: { color: TEXT, fontSize: 14, fontWeight: 600 },
  range: {
    category: accentRange,
    ordinal: accentRange,
    heatmap: heatRange,
    ramp: heatRange,
    diverging: divergingRange,
  },
  bar: { cornerRadiusEnd: 1 },
  line: { strokeWidth: 3 },
  area: { opacity: 0.7 },
};

function mergeConfig(base: Config, extra?: Config): Config {
  if (!extra) return base;
  return {
    ...base,
    ...extra,
    axis: { ...base.axis, ...extra.axis },
    legend: { ...base.legend, ...extra.legend },
    header: { ...base.header, ...extra.header },
    title: { ...base.title, ...extra.title },
    range: { ...base.range, ...extra.range },
  };
}

export function withVizTheme(spec: VisualizationSpec): VisualizationSpec {
  // Avoid strict autosize typing clashes by treating autosize as passthrough.
  const cleaned = { ...(spec as Record<string, unknown>) };
  const nextConfig = mergeConfig(baseConfig, spec.config as Config | undefined);
  return {
    ...cleaned,
    background: "transparent",
    config: nextConfig,
  } as VisualizationSpec;
}
