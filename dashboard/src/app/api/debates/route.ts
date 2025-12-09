import path from "path";
import { resolveRun } from "@/lib/server/runs";
import { fetchObjectStream } from "@/lib/server/s3";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const runId = new URL(request.url).searchParams.get("run") || undefined;
  let run;
  try {
    run = await resolveRun(runId);
  } catch (err) {
    if (err instanceof Error && err.message === "unknown_run") {
      return new Response(JSON.stringify({ error: "unknown_run" }), { status: 400, headers: { "Content-Type": "application/json" } });
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
  } catch {
    return new Response("Failed to fetch object", { status: 502 });
  }
}
