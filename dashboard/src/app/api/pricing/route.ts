import { NextResponse } from "next/server";
import { pricingSnapshot, PricingSnapshot } from "@/lib/pricing";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type OpenRouterModel = {
  id: string;
  pricing?: {
    prompt?: number | null;
    completion?: number | null;
    cached?: number | null;
  };
  provider?: { name?: string };
};

const ALIASES: Record<string, string> = {
  "gpt-4.1": "openai/gpt-4.1",
  "gpt-4.1-mini": "openai/gpt-4.1-mini",
  "gpt-4o-mini": "openai/gpt-4o-mini",
  "gpt-4o": "openai/gpt-4o",
  "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
  "claude-3.5-haiku": "anthropic/claude-3.5-haiku",
  "claude-3-opus": "anthropic/claude-3-opus",
  "gemini-1.5-pro": "google/gemini-1.5-pro",
  "gemini-1.5-flash": "google/gemini-1.5-flash",
};

const cache = new Map<string, { ts: number; data: PricingSnapshot }>();
const TTL_MS = 24 * 60 * 60 * 1000;

function resolveId(id: string) {
  return ALIASES[id] || id;
}

async function fetchOpenRouterModels(apiKey: string): Promise<OpenRouterModel[]> {
  const res = await fetch("https://openrouter.ai/api/v1/models", {
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`openrouter models failed: ${res.status}`);
  const json = await res.json();
  return json?.data ?? [];
}

function buildSnapshot(rows: PricingSnapshot["rows"], source: "live" | "snapshot"): PricingSnapshot {
  return {
    updated: new Date().toISOString().slice(0, 10),
    currency: "USD",
    source,
    rows,
  };
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const idsParam = url.searchParams.get("ids");
  if (!idsParam) {
    return NextResponse.json({ ...pricingSnapshot, source: "snapshot" });
  }
  const ids = idsParam
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const cacheKey = ids.sort().join(",");

  const now = Date.now();
  const cached = cache.get(cacheKey);
  if (cached && now - cached.ts < TTL_MS) {
    return NextResponse.json(cached.data);
  }

  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    const snap = { ...pricingSnapshot, source: "snapshot" as const };
    cache.set(cacheKey, { ts: now, data: snap });
    return NextResponse.json(snap);
  }

  try {
    const models = await fetchOpenRouterModels(apiKey);
    const map = new Map<string, OpenRouterModel>();
    for (const m of models) {
      map.set(m.id, m);
      const parts = m.id.split("/");
      const bare = parts[parts.length - 1];
      map.set(bare, m);
      map.set(bare.toLowerCase(), m);
    }
    const rows = ids.map((id) => {
      const resolved = resolveId(id);
      const model = map.get(resolved) || map.get(resolved.toLowerCase()) || map.get(id) || map.get(id.toLowerCase());
      if (!model || !model.pricing) {
        const fallback = pricingSnapshot.rows.find((r) => r.model_id === id);
        return (
          fallback || {
            model_id: id,
            provider: model?.provider?.name || "unknown",
            input_per_million: 0,
            output_per_million: 0,
          }
        );
      }
      const prompt = Number(model.pricing.prompt ?? model.pricing.cached ?? 0);
      const completion = Number(model.pricing.completion ?? model.pricing.cached ?? 0);
      const input = prompt * 1_000_000;
      const output = completion * 1_000_000;
      return {
        model_id: id,
        provider: model.provider?.name || "openrouter",
        input_per_million: Number(input.toFixed(4)),
        output_per_million: Number(output.toFixed(4)),
      };
    });
    const payload = buildSnapshot(rows, "live");
    cache.set(cacheKey, { ts: now, data: payload });
    return NextResponse.json(payload);
  } catch {
    const snap = { ...pricingSnapshot, source: "snapshot" as const };
    cache.set(cacheKey, { ts: now, data: snap });
    return NextResponse.json(snap, { status: 200 });
  }
}
