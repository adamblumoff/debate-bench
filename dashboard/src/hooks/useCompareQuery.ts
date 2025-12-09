"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { MAX_COMPARE } from "@/lib/compareLimits";

export function useCompareQuery(max = MAX_COMPARE) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const searchString = useMemo(() => searchParams.toString(), [searchParams]);

  const parseParams = useCallback(() => {
    const params = searchParams;
    const values = params.getAll("compare");
    if (values.length === 1 && values[0].includes(",")) {
      return Array.from(new Set(values[0].split(",").filter(Boolean))).slice(
        0,
        max,
      );
    }
    return Array.from(new Set(values)).slice(0, max);
  }, [searchParams, max]);

  const [selected, setSelected] = useState<string[]>(parseParams);

  useEffect(() => {
    setSelected(parseParams());
  }, [parseParams]);

  const addModel = useCallback(
    (id: string) => {
      setSelected((prev) => {
        if (prev.includes(id)) return prev;
        return [...prev, id].slice(-max);
      });
    },
    [max],
  );

  const removeModel = useCallback((id: string) => {
    setSelected((prev) => {
      return prev.filter((m) => m !== id);
    });
  }, []);

  useEffect(() => {
    const current = searchString;
    const params = new URLSearchParams(current);
    params.delete("compare");
    selected.forEach((c) => params.append("compare", c));
    const nextString = params.toString();
    if (nextString === current) return;
    const href = nextString ? `?${nextString}` : window.location.pathname;
    router.replace(href, { scroll: false });
  }, [router, searchString, selected]);

  return { selected, addModel, removeModel };
}
