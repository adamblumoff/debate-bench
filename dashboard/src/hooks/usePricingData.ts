"use client";

import { useEffect, useState } from "react";
import { pricingSnapshot, PricingSnapshot } from "@/lib/pricing";

export function usePricingData(modelIds: string[]): PricingSnapshot {
  const [data, setData] = useState<PricingSnapshot>({ ...pricingSnapshot, source: "snapshot" });

  useEffect(() => {
    if (!modelIds.length) return;
    const controller = new AbortController();
    const idsParam = encodeURIComponent(modelIds.join(","));
    fetch(`/api/pricing?ids=${idsParam}`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`pricing http ${res.status}`);
        return res.json();
      })
      .then((next) => setData(next as PricingSnapshot))
      .catch(() => {
        setData({ ...pricingSnapshot, source: "snapshot" });
      });
    return () => controller.abort();
  }, [modelIds]);

  return data;
}
