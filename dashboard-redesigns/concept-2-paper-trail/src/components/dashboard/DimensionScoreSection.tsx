"use client";

import { useMemo, useState } from "react";
import { VisualizationSpec } from "vega-embed";
import { DerivedData } from "@/lib/types";
import { ChevronDown } from "lucide-react";
import { VegaLiteChart } from "@/components/VegaLiteChart";
import { ChartCard } from "@/components/ChartCard";
import { heatRange } from "@/lib/vegaTheme";
import posthog from "posthog-js";

type Props = {
  derived: DerivedData;
  selectedModels: string[];
};

type HeatRow = {
  topic_id: string;
  model: string;
  mean: number;
  samples: number;
};

export function DimensionScoreSection({ derived, selectedModels }: Props) {
  const [dimension, setDimension] = useState<string>(
    derived.dimensions[0] ?? "",
  );

  const activeDimension = useMemo(() => {
    if (derived.dimensions.includes(dimension)) return dimension;
    return derived.dimensions[0] ?? "";
  }, [derived.dimensions, dimension]);

  const allowedModels = useMemo(() => {
    if (!selectedModels.length) return null;
    return new Set(selectedModels);
  }, [selectedModels]);

  const heatValues = useMemo(() => {
    if (!activeDimension) return [] as HeatRow[];
    return derived.topicDimensionStats
      .filter((row) => row.dimension === activeDimension)
      .filter((row) => !allowedModels || allowedModels.has(row.model_id))
      .map((row) => ({
        topic_id: row.topic_id,
        model: row.model_id,
        mean: row.mean,
        samples: row.samples,
      }));
  }, [derived.topicDimensionStats, activeDimension, allowedModels]);

  const heatSpec = useMemo((): VisualizationSpec | null => {
    if (!heatValues.length) return null;
    return {
      width: "container",
      height: 320,
      data: { values: heatValues },
      mark: { type: "rect" },
      encoding: {
        x: {
          field: "topic_id",
          type: "nominal",
          sort: "-y",
          axis: { labelAngle: -35, labelLimit: 120 },
        },
        y: { field: "model", type: "nominal" },
        color: {
          field: "mean",
          type: "quantitative",
          scale: { range: heatRange },
        },
        tooltip: [
          { field: "model", title: "Model" },
          { field: "topic_id", title: "Topic" },
          { field: "mean", title: "Mean score", format: ".3f" },
          { field: "samples", title: "Samples" },
        ],
      },
      config: { axis: { labelLimit: 120 } },
    } satisfies VisualizationSpec;
  }, [heatValues]);

  const hasData = heatValues.length > 0;

  return (
    <section id="dimensions" className="grid gap-4 md:grid-cols-12">
      <div className="md:col-span-12 min-w-0">
        <ChartCard
          title="Judge dimension scores"
          subtitle="Model averages from judge dimension scores (merged across pro/con)."
          className="chart-card h-full"
        >
          {!hasData ? (
            <div className="flex h-full min-h-[240px] items-center justify-center text-sm text-[var(--text-muted)]">
              No dimension scores available for this selection.
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex justify-center">
                <div className="relative">
                  <select
                    className="appearance-none rounded-[2px] border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-1 pr-8 text-xs font-semibold uppercase text-[var(--text-primary)] focus:outline-none focus:ring-0 focus-visible:border-[var(--text-primary)]"
                    value={activeDimension}
                    onChange={(e) => {
                      const next = e.target.value;
                      setDimension(next);
                      posthog.capture("dimension_chart_dimension_changed", {
                        dimension: next,
                      });
                    }}
                  >
                    {derived.dimensions.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-primary)]"
                    aria-hidden="true"
                  />
                </div>
              </div>
              {heatSpec && <VegaLiteChart spec={heatSpec} />}
            </div>
          )}
        </ChartCard>
      </div>
    </section>
  );
}
