"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function useCompareQuery(max = 4) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const parseParams = useCallback(() => {
    const params = searchParams;
    const values = params.getAll("compare");
    if (values.length === 1 && values[0].includes(",")) {
      return values[0].split(",").filter(Boolean);
    }
    return values;
  }, [searchParams]);

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
    [max]
  );

  const removeModel = useCallback(
    (id: string) => {
      setSelected((prev) => {
        return prev.filter((m) => m !== id);
      });
    },
    []
  );

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("compare");
    selected.forEach((c) => params.append("compare", c));
    const query = params.toString();
    const href = query ? `?${query}` : ".";
    router.replace(href, { scroll: false });
  }, [router, searchParams, selected]);

  return { selected, addModel, removeModel };
}
