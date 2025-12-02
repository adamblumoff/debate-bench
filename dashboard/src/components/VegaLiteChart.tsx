"use client";

import { VegaEmbed, VisualizationSpec } from "react-vega";

export function VegaLiteChart({ spec }: { spec: VisualizationSpec }) {
  return <VegaEmbed spec={spec} options={{ actions: false }} className="w-full" />;
}
