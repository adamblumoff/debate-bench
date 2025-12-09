"use client";

import { create } from "zustand";
import useSWR from "swr";
import { DerivedData } from "@/lib/types";
import { MetricsResponse } from "@/lib/apiTypes";

interface DataState {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  derived?: DerivedData;
  derivedByCategory?: Record<string, DerivedData>;
  meta?: { debateCount: number; modelCount: number; categories: string[] };
  currentRun?: string;
  _requestId?: number;
  load: (runId?: string, refresh?: boolean) => Promise<void>;
}

export const useDataStore = create<DataState>((set, get) => ({
  status: "idle",
  _requestId: 0,
  load: async (runId, refresh = false) => {
    if (
      !refresh &&
      (get().status === "loading" || get().status === "ready") &&
      get().currentRun === runId
    )
      return;
    const current = get();
    const reqId = (current._requestId ?? 0) + 1;
    set({ _requestId: reqId });
    try {
      set({
        status: "loading",
        error: undefined,
        derived: undefined,
        derivedByCategory: undefined,
        meta: undefined,
      });
      const qsParts = [] as string[];
      if (runId) qsParts.push(`run=${encodeURIComponent(runId)}`);
      if (refresh) qsParts.push("refresh=1");
      const qs = qsParts.length ? `?${qsParts.join("&")}` : "";
      const res = await fetch(`/api/metrics${qs}`);
      if (!res.ok) throw new Error(`Failed fetch /api/metrics: ${res.status}`);
      const json: MetricsResponse = await res.json();
      if (get()._requestId !== reqId) return;
      set({
        status: "ready",
        derived: json.derived,
        derivedByCategory: json.derivedByCategory,
        meta: json.meta,
        currentRun: runId,
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown error";
      if (get()._requestId !== reqId) return;
      set({ status: "error", error: message });
    }
  },
}));

export const useEnsureData = (runId?: string) => {
  const load = useDataStore((s) => s.load);
  const status = useDataStore((s) => s.status);
  const key = runId ? `metrics-${runId}` : "metrics-default";
  useSWR(
    status === "idle" || useDataStore.getState().currentRun !== runId
      ? key
      : null,
    () => load(runId),
  );
  return useDataStore();
};
