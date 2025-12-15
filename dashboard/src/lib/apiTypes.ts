import { DerivedData, RecentCostSummary } from "@/lib/types";
import { RunConfig } from "@/lib/server/runs";
import { PricingSnapshot } from "@/lib/pricing";

export type ManifestResponse = {
  runs: RunConfig[];
  defaultRunId: string;
};

export type MetricsMeta = {
  debateCount: number;
  modelCount: number;
  categories: string[];
};

export type MetricsResponse = {
  derived: DerivedData;
  derivedByCategory: Record<string, DerivedData>;
  meta: MetricsMeta;
  recentCost: RecentCostSummary;
};

export type PricingResponse = PricingSnapshot & { source: "live" | "snapshot" };
