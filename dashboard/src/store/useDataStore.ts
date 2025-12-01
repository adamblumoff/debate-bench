"use client";

import { create } from "zustand";
import useSWR from "swr";
import { DebateRecord, DerivedData } from "@/lib/types";
import { parseJsonlStream } from "@/lib/jsonl";
import { buildDerived } from "@/lib/metrics";

interface DataState {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  debates: DebateRecord[];
  derived?: DerivedData;
  load: () => Promise<void>;
}

const fetchJson = async <T>(url: string): Promise<T> => {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed fetch ${url}: ${res.status}`);
  return res.json();
};

export const useDataStore = create<DataState>((set, get) => ({
  status: "idle",
  debates: [],
  load: async () => {
    if (get().status === "loading" || get().status === "ready") return;
    try {
      set({ status: "loading", error: undefined });
      const manifest = await fetchJson<{ runs: { id: string; key: string }[] }>("/api/manifest");
      const run = manifest.runs[0];
      const signed = await fetchJson<{ url: string }>(`/api/sign?key=${encodeURIComponent(run.key)}`);
      const debates = await parseJsonlStream<DebateRecord>(signed.url);
      const derived = buildDerived(debates);
      set({ status: "ready", debates, derived });
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
