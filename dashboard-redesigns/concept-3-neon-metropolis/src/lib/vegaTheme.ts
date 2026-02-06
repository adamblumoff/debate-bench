import { VisualizationSpec } from "vega-embed";
import { Config } from "vega-lite";

const TEXT = "#e0e0ff";
const MUTED = "#7878aa";
const BORDER = "#2a2a5e";

export const accentRange = [
  "#ff00aa",
  "#ff44cc",
  "#cc66ff",
  "#8866ff",
  "#44aaff",
  "#00ffcc",
];
export const heatRange = [
  "#0a0a12",
  "#1a0a30",
  "#30105a",
  "#5a1a8a",
  "#8a30c0",
  "#ff00aa",
];
export const divergingRange = [
  "#00ffcc",
  "#66ffd9",
  "#e0e0ff",
  "#ff88dd",
  "#ff00aa",
  "#aa0066",
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
