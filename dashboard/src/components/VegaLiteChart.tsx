"use client";

import { VegaLite, VisualizationSpec } from "react-vega";

export function VegaLiteChart({ spec }: { spec: VisualizationSpec }) {
  return <VegaLite spec={spec} actions={false} className="w-full" />;
}
