import path from "path";
import { resolveRun } from "@/lib/server/runs";
import { fetchObjectStream } from "@/lib/server/s3";
import { rateLimit } from "@/lib/rateLimit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const limit = rateLimit(request, "debates", {
    capacity: Number(process.env.RL_DEBATES_CAPACITY || 10),
    refillMs: Number(process.env.RL_DEBATES_REFILL_MS || 60_000),
  });
  if (!limit.ok) {
    return new Response(JSON.stringify({ error: "rate_limited" }), {
      status: 429,
      headers: {
        "Content-Type": "application/json",
        "Retry-After": `${Math.ceil((limit.reset - Date.now()) / 1000)}`,
      },
    });
  }

  const runId = new URL(request.url).searchParams.get("run") || undefined;
  let run;
  try {
    run = await resolveRun(runId);
  } catch (err) {
    if (err instanceof Error && err.message === "unknown_run") {
      return new Response(JSON.stringify({ error: "unknown_run" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }
    throw err;
  }

  try {
    const { body, contentType } = await fetchObjectStream(run);
    const filename = run.key ? path.basename(run.key) : "debates.jsonl";
    return new Response(body, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    const status =
      err instanceof Error && /timeout/i.test(err.message) ? 504 : 502;
    return new Response(
      JSON.stringify({
        error: "fetch_failed",
        detail: err instanceof Error ? err.message : "unknown",
      }),
      {
        status,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
}
