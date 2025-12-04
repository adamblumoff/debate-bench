"use client";

import { useEffect, useMemo, useState } from "react";
import { pricingSnapshot, PricingSnapshot } from "@/lib/pricing";

export function usePricingData(modelIds: string[], runId?: string): PricingSnapshot {
  const [data, setData] = useState<PricingSnapshot>({ ...pricingSnapshot, source: "snapshot" });

  const idsKey = useMemo(() => modelIds.filter(Boolean).join(","), [modelIds]);

  useEffect(() => {
    if (!idsKey) return;
    const controller = new AbortController();
    const idsParam = encodeURIComponent(idsKey);
    const runParam = runId ? `&run=${encodeURIComponent(runId)}` : "";
    fetch(`/api/pricing?ids=${idsParam}${runParam}`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`pricing http ${res.status}`);
        const json = await res.json();
        if (!json || typeof json !== "object" || !Array.isArray(json.rows)) {
          throw new Error("Invalid pricing response format");
        }
        return json;
      })
      .then((next) => setData(next as PricingSnapshot))
      .catch((err) => {
        if (err.name !== "AbortError") {
          setData({ ...pricingSnapshot, source: "snapshot" });
        }
      });
    return () => controller.abort();
  }, [idsKey, runId]);

  return data;
}
