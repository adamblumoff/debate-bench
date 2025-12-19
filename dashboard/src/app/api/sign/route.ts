import { NextRequest, NextResponse } from "next/server";
import { serverEnv } from "@/lib/env";
import { resolveRun } from "@/lib/server/runs";
import { getSignedObjectUrl } from "@/lib/server/s3";
import { rateLimit } from "@/lib/rateLimit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const limit = rateLimit(req, "sign", {
    capacity: Number(process.env.RL_SIGN_CAPACITY || 20),
    refillMs: Number(process.env.RL_SIGN_REFILL_MS || 60_000),
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
  const runId = req.nextUrl.searchParams.get("run") || undefined;
  let run;
  try {
    run = await resolveRun(runId);
  } catch (err) {
    if (err instanceof Error && err.message === "unknown_run") {
      return NextResponse.json({ error: "unknown_run" }, { status: 400 });
    }
    throw err;
  }

  const key = req.nextUrl.searchParams.get("key") || run.key;
  if (key !== run.key) {
    return NextResponse.json({ error: "Key not allowed" }, { status: 400 });
  }
  const expiresIn = serverEnv.urlExpirySeconds;
  try {
    const url = await getSignedObjectUrl(run, key, expiresIn);
    return NextResponse.json({ url, expiresIn });
  } catch (err) {
    const status =
      err instanceof Error && /timeout/i.test(err.message) ? 504 : 502;
    return NextResponse.json(
      {
        error: "sign_failed",
        detail: err instanceof Error ? err.message : "unknown",
      },
      { status },
    );
  }
}
