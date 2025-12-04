import { NextResponse } from "next/server";
import { rateLimit } from "@/lib/rateLimit";
import { getMetrics } from "@/lib/server/metrics";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const limit = rateLimit(request, "metrics", {
    capacity: Number(process.env.RL_METRICS_CAPACITY || 20),
    refillMs: Number(process.env.RL_METRICS_REFILL_MS || 60_000),
  });
  if (!limit.ok) {
    return NextResponse.json({ error: "rate_limited" }, { status: 429, headers: { "Retry-After": `${Math.ceil((limit.reset - Date.now()) / 1000)}` } });
  }

  const url = new URL(request.url);
  const refresh = url.searchParams.get("refresh") === "1";
  const runId = url.searchParams.get("run") || undefined;
  try {
    const payload = await getMetrics(refresh, runId);
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    if (err instanceof Error && err.message === "unknown_run") {
      return NextResponse.json({ error: "unknown_run" }, { status: 400 });
    }
    throw err;
  }
}
