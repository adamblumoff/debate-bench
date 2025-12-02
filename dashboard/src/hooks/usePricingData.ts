"use client";

import { useEffect, useState } from "react";
import { fetchPricing, pricingSnapshot, PricingSnapshot } from "@/lib/pricing";

export function usePricingData(): PricingSnapshot {
  const [data, setData] = useState<PricingSnapshot>(pricingSnapshot);

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_PRICING_URL;
    if (!url) return;
    fetchPricing(url)
      .then((next) => setData(next))
      .catch(() => {
        // fallback to bundled snapshot
      });
  }, []);

  return data;
}
