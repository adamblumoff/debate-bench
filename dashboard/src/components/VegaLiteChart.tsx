"use client";

import { useMemo } from "react";
import { VegaEmbed } from "react-vega";
import { VisualizationSpec } from "vega-embed";
import { withVizTheme } from "@/lib/vegaTheme";

export function VegaLiteChart({ spec }: { spec: VisualizationSpec }) {
  const themed = useMemo(() => withVizTheme(spec), [spec]);
  return (
    <VegaEmbed spec={themed} options={{ actions: false }} className="w-full" />
  );
}
