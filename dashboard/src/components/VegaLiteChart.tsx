"use client";

import { VegaEmbed } from "react-vega";
import { VisualizationSpec } from "vega-embed";

export function VegaLiteChart({ spec }: { spec: VisualizationSpec }) {
  return <VegaEmbed spec={spec} options={{ actions: false }} className="w-full" />;
}
