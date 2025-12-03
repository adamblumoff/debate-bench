"use client";

import { useEffect, useMemo, useState } from "react";
import { pricingSnapshot, PricingSnapshot } from "@/lib/pricing";

export function usePricingData(modelIds: string[]): PricingSnapshot {
  const [data, setData] = useState<PricingSnapshot>({ ...pricingSnapshot, source: "snapshot" });

  const idsKey = useMemo(() => modelIds.filter(Boolean).join(","), [modelIds]);

  useEffect(() => {
    if (!idsKey) return;
    const controller = new AbortController();
    const idsParam = encodeURIComponent(idsKey);
    fetch(`/api/pricing?ids=${idsParam}`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`pricing http ${res.status}`);
        return res.json();
      })
      .then((next) => setData(next as PricingSnapshot))
      .catch((err) => {
        if (err.name !== "AbortError") {
          setData({ ...pricingSnapshot, source: "snapshot" });
        }
      });
    return () => controller.abort();
  }, [idsKey]);

  return data;
}
