import { NextResponse } from "next/server";
import { rateLimit } from "@/lib/rateLimit";
import { getMetrics } from "@/lib/server/metrics";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const limit = rateLimit(
    request,
    "metrics",
    {
      capacity: Number(process.env.RL_METRICS_CAPACITY || 20),
      refillMs: Number(process.env.RL_METRICS_REFILL_MS || 60_000),
    },
    (info) => {
      if (!info.ok) {
        console.warn(
          `[rate-limit] metrics blocked ip=${info.ipHash} reset=${info.reset}`,
        );
      }
    },
  );
  if (!limit.ok) {
    return NextResponse.json(
      { error: "rate_limited" },
      {
        status: 429,
        headers: {
          "Retry-After": `${Math.ceil((limit.reset - Date.now()) / 1000)}`,
        },
      },
    );
  }

  const url = new URL(request.url);
  const refresh = url.searchParams.get("refresh") === "1";
  const full = url.searchParams.get("full") === "1";
  const runId = url.searchParams.get("run") || undefined;
  try {
    const payload = await getMetrics(refresh, runId, undefined, {
      includeRows: full,
    });
    const cacheHeader = refresh
      ? "no-store"
      : "public, max-age=0, s-maxage=300, stale-while-revalidate=900";
    return NextResponse.json(payload, {
      headers: { "Cache-Control": cacheHeader },
    });
  } catch (err) {
    if (
      err instanceof Error &&
      /parse_error|too_large|timeout/i.test(err.message)
    ) {
      return NextResponse.json({ error: err.message }, { status: 422 });
    }
    if (err instanceof Error && err.message === "unknown_run") {
      return NextResponse.json({ error: "unknown_run" }, { status: 400 });
    }
    throw err;
  }
}
