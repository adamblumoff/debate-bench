"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import { VisualizationSpec } from "vega-embed";
import { withVizTheme } from "@/lib/vegaTheme";

const VegaEmbed = dynamic(
  () => import("react-vega").then((m) => m.VegaEmbed),
  { ssr: false },
);

export function VegaLiteChart({ spec }: { spec: VisualizationSpec }) {
  const themed = useMemo(() => withVizTheme(spec), [spec]);
  return (
    <div className="w-full min-w-0 overflow-x-auto">
      <VegaEmbed
        spec={themed}
        options={{ actions: false }}
        className="w-full"
      />
    </div>
  );
}
