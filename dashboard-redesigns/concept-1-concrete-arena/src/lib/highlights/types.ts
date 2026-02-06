import { VisualizationSpec } from "vega-embed";

export type HighlightSpecs = {
  sideBias?: VisualizationSpec;
  judgeSideBiasCv?: VisualizationSpec;
  categoryHeat?: VisualizationSpec;
  tokens?: VisualizationSpec;
  ratingVsWin?: VisualizationSpec;
  pricePerf?: VisualizationSpec;
  h2h?: VisualizationSpec;
  judgeHeat?: VisualizationSpec;
};

export type HighlightLists = {
  elo: { label: string; value: number; hint?: string }[];
  win: { label: string; value: number; hint?: string }[];
  tokens: { label: string; prompt: number; output: number }[];
  cost: { label: string; value: number; hint?: string }[];
  sideBias: { label: string; value: number; hint?: string }[];
};

export type KpiItem = {
  label: string;
  value: string;
  helper?: string;
};

export type Kpi = {
  topModel: KpiItem;
  sideGap: KpiItem;
  judgeSpan: KpiItem;
} | null;
