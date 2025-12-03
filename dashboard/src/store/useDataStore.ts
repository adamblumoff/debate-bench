"use client";

import { create } from "zustand";
import useSWR from "swr";
import { DerivedData } from "@/lib/types";

interface DataState {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  derived?: DerivedData;
  derivedByCategory?: Record<string, DerivedData>;
  meta?: { debateCount: number; modelCount: number; categories: string[] };
  load: () => Promise<void>;
}

export const useDataStore = create<DataState>((set, get) => ({
  status: "idle",
  load: async () => {
    if (get().status === "loading" || get().status === "ready") return;
    try {
      set({ status: "loading", error: undefined });
      const res = await fetch("/api/metrics");
      if (!res.ok) throw new Error(`Failed fetch /api/metrics: ${res.status}`);
      const json = await res.json();
      set({ status: "ready", derived: json.derived, derivedByCategory: json.derivedByCategory, meta: json.meta });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown error";
      set({ status: "error", error: message });
    }
  },
}));

export const useEnsureData = () => {
  const load = useDataStore((s) => s.load);
  const status = useDataStore((s) => s.status);
  useSWR(status === "idle" ? "debates" : null, () => load());
  return useDataStore();
};
