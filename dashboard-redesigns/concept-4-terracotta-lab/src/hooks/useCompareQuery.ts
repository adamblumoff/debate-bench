"use client";

import { useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { MAX_COMPARE } from "@/lib/compareLimits";
import posthog from "posthog-js";

export function useCompareQuery(max = MAX_COMPARE, enabled = true) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const parseParams = useCallback(() => {
    if (!enabled) return [];
    const values = searchParams.getAll("compare");
    if (values.length === 1 && values[0].includes(",")) {
      return Array.from(new Set(values[0].split(",").filter(Boolean))).slice(
        0,
        max,
      );
    }
    return Array.from(new Set(values)).slice(0, max);
  }, [searchParams, max, enabled]);

  const selected = useMemo(() => parseParams(), [parseParams]);

  const writeSelection = useCallback(
    (next: string[]) => {
      if (!enabled) return;
      const params = new URLSearchParams(searchParams.toString());
      params.delete("compare");
      next.forEach((c) => params.append("compare", c));
      const nextString = params.toString();
      const href = nextString ? `?${nextString}` : window.location.pathname;
      router.replace(href, { scroll: false });
    },
    [router, searchParams, enabled],
  );

  const addModel = useCallback(
    (id: string) => {
      if (!enabled) return;
      if (selected.includes(id)) return;
      const next = [...selected, id].slice(-max);
      writeSelection(next);
      posthog.capture("model_added_to_compare", {
        model_id: id,
        total_selected: next.length,
      });
    },
    [max, enabled, selected, writeSelection],
  );

  const removeModel = useCallback(
    (id: string) => {
      if (!enabled) return;
      const next = selected.filter((m) => m !== id);
      writeSelection(next);
      posthog.capture("model_removed_from_compare", {
        model_id: id,
        remaining_selected: next.length,
      });
    },
    [enabled, selected, writeSelection],
  );

  return { selected, addModel, removeModel };
}
