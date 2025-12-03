import { VisualizationSpec } from "vega-embed";
import { Config } from "vega-lite";

const TEXT = "#e9eef7";
const MUTED = "#98a7bf";
const BORDER = "#1f2c3a";

export const accentRange = ["#4dd3ff", "#6fe1ff", "#8fc7ff", "#b5e8ff", "#d9f7ff", "#7cc0ff"];
export const heatRange = ["#0f1f2a", "#0d3a46", "#0f5560", "#1f7a8a", "#3aa9b5", "#6dd3e3"];
export const divergingRange = ["#f9706d", "#f6b44f", "#e9eef7", "#63c7ff", "#3b9fff", "#1f7aad"];

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
  bar: { cornerRadiusEnd: 3 },
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
