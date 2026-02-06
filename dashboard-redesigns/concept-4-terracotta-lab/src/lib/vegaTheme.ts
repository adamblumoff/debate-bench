import { VisualizationSpec } from "vega-embed";
import { Config } from "vega-lite";

const TEXT = "#2c2418";
const MUTED = "#9a8b78";
const BORDER = "#ddd5c8";

export const accentRange = [
  "#c4663a",
  "#d4916a",
  "#b8a88e",
  "#8c9a6e",
  "#6a8a5a",
  "#4a7a68",
];
export const heatRange = [
  "#f2ede5",
  "#e8dcc8",
  "#d4c4a0",
  "#b8a068",
  "#9a7a40",
  "#c4663a",
];
export const divergingRange = [
  "#4a7a68",
  "#7aaa90",
  "#f2ede5",
  "#d4916a",
  "#c4663a",
  "#8a3a1a",
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
  bar: { cornerRadiusEnd: 12 },
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
