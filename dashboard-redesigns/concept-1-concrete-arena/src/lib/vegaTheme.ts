import { VisualizationSpec } from "vega-embed";
import { Config } from "vega-lite";

const TEXT = "#f0f0f0";
const MUTED = "#999999";
const BORDER = "#444444";

export const accentRange = [
  "#ff3d00",
  "#ff6e40",
  "#ff9e80",
  "#ffccbc",
  "#fbe9e7",
  "#ff8a65",
];
export const heatRange = [
  "#1a1a1a",
  "#3e2723",
  "#4e342e",
  "#6d4c41",
  "#8d6e63",
  "#ff3d00",
];
export const divergingRange = [
  "#2979ff",
  "#82b1ff",
  "#f0f0f0",
  "#ff8a65",
  "#ff3d00",
  "#bf360c",
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
  bar: { cornerRadiusEnd: 0 },
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
