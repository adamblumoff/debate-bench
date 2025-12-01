"use client";

import dynamic from "next/dynamic";
import { VisualizationSpec } from "vega-embed";

const VegaLite = dynamic(() => import("react-vega").then((m) => m.VegaLite), { ssr: false });

export function VegaLiteChart({ spec }: { spec: VisualizationSpec }) {
  return <VegaLite spec={spec} actions={false} className="w-full" />;
}
