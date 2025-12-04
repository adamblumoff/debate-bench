import { serverEnv } from "@/lib/env";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { resolveRun } from "@/lib/server/runs";

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

  const s3 = new S3Client({ region: run.region });
  const command = new GetObjectCommand({ Bucket: run.bucket, Key: run.key });
  const url = await getSignedUrl(s3, command, { expiresIn: serverEnv.urlExpirySeconds });

  const res = await fetch(url);
  if (!res.ok || !res.body) {
    return new Response("Failed to fetch object", { status: 502 });
  }

  return new Response(res.body, {
    status: 200,
    headers: {
      "Content-Type": res.headers.get("Content-Type") || "application/jsonl",
      "Cache-Control": "no-store",
    },
  });
}
