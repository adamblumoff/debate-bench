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

  const updateQuery = useCallback(
    (next: string[]) => {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("compare");
      next.forEach((c) => params.append("compare", c));
      router.replace(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const addModel = useCallback(
    (id: string) => {
      setSelected((prev) => {
        if (prev.includes(id)) return prev;
        const next = [...prev, id].slice(-max);
        updateQuery(next);
        return next;
      });
    },
    [max, updateQuery]
  );

  const removeModel = useCallback(
    (id: string) => {
      setSelected((prev) => {
        const next = prev.filter((m) => m !== id);
        updateQuery(next);
        return next;
      });
    },
    [updateQuery]
  );

  return { selected, addModel, removeModel };
}
