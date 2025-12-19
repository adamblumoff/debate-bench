"use client";

import { create } from "zustand";
import useSWR from "swr";
import { CostSummary, DerivedData } from "@/lib/types";
import { MetricsResponse } from "@/lib/apiTypes";

interface DataState {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  derived?: DerivedData;
  derivedByCategory?: Record<string, DerivedData>;
  meta?: { debateCount: number; modelCount: number; categories: string[] };
  costSummary?: CostSummary;
  currentRun?: string;
  _requestId?: number;
  _biasCvLoaded?: Record<string, boolean>;
  _biasCvLoading?: Record<string, boolean>;
  load: (runId?: string, refresh?: boolean) => Promise<void>;
  loadBiasCv: (runId?: string, refresh?: boolean) => Promise<void>;
}

export const useDataStore = create<DataState>((set, get) => ({
  status: "idle",
  _requestId: 0,
  _biasCvLoaded: {},
  _biasCvLoading: {},
  load: async (runId, refresh = false) => {
    if (
      !refresh &&
      (get().status === "loading" || get().status === "ready") &&
      get().currentRun === runId
    )
      return;
    const runKey = runId || "default";
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
        costSummary: undefined,
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
        costSummary: json.costSummary,
        currentRun: runId,
        _biasCvLoaded: { ...(get()._biasCvLoaded || {}), [runKey]: false },
        _biasCvLoading: { ...(get()._biasCvLoading || {}), [runKey]: false },
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown error";
      if (get()._requestId !== reqId) return;
      set({ status: "error", error: message });
    }
  },
  loadBiasCv: async (runId, refresh = false) => {
    const state = get();
    if (state.status !== "ready") return;
    const runKey = runId || "default";
    if (state._biasCvLoaded?.[runKey] || state._biasCvLoading?.[runKey]) return;
    set({
      _biasCvLoading: { ...(get()._biasCvLoading || {}), [runKey]: true },
    });
    const qsParts = ["bias=full"] as string[];
    if (runId) qsParts.push(`run=${encodeURIComponent(runId)}`);
    if (refresh) qsParts.push("refresh=1");
    const qs = qsParts.length ? `?${qsParts.join("&")}` : "";
    try {
      const res = await fetch(`/api/metrics${qs}`);
      if (!res.ok) {
        set({
          _biasCvLoading: { ...(get()._biasCvLoading || {}), [runKey]: false },
        });
        return;
      }
      const json: MetricsResponse = await res.json();
      if (get().currentRun !== runId) return;
      set({
        derived: json.derived,
        derivedByCategory: json.derivedByCategory,
        meta: json.meta,
        costSummary: json.costSummary,
        _biasCvLoaded: { ...(get()._biasCvLoaded || {}), [runKey]: true },
        _biasCvLoading: { ...(get()._biasCvLoading || {}), [runKey]: false },
      });
    } catch {
      // leave base metrics intact on failure
      set({
        _biasCvLoading: { ...(get()._biasCvLoading || {}), [runKey]: false },
      });
    }
  },
}));

export const useEnsureData = (runId?: string, enabled: boolean = true) => {
  const load = useDataStore((s) => s.load);
  const status = useDataStore((s) => s.status);
  const key = runId ? `metrics-${runId}` : "metrics-default";
  useSWR(
    enabled &&
      (status === "idle" || useDataStore.getState().currentRun !== runId)
      ? key
      : null,
    () => load(runId),
  );
  return useDataStore();
};
