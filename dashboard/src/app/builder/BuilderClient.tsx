"use client";

import { VisualizationSpec } from "vega-embed";

type Props = {
  allModels: string[];
  selectedModels: string[];
  fields: string[];
  initialSpec: VisualizationSpec | null;
  initialRequest: {
    dataset: string;
    chartType: string;
    xField: string;
    yField?: string;
    colorField?: string;
  };
};

export default function BuilderClient(_props: Props) {
  return (
    <div className="card">
      <p className="text-slate-300 text-sm">Loading builder…</p>
    </div>
  );
}
