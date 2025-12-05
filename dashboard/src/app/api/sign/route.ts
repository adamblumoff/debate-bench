import { NextRequest, NextResponse } from "next/server";
import { serverEnv } from "@/lib/env";
import { resolveRun } from "@/lib/server/runs";
import { getSignedObjectUrl } from "@/lib/server/s3";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
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
  const url = await getSignedObjectUrl(run, key, expiresIn);
  return NextResponse.json({ url, expiresIn });
}
