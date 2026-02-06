import { NextResponse } from "next/server";
import { getRuns } from "@/lib/server/runs";
import { rateLimit } from "@/lib/rateLimit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const limit = rateLimit(request, "manifest", {
    capacity: Number(process.env.RL_MANIFEST_CAPACITY || 30),
    refillMs: Number(process.env.RL_MANIFEST_REFILL_MS || 60_000),
  });
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
  const refresh = new URL(request.url).searchParams.get("refresh") === "1";
  const payload = await getRuns(refresh);
  return NextResponse.json(payload);
}
