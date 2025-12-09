import { GetObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { serverEnv } from "@/lib/env";
import { fetchWithTimeout } from "@/lib/server/validate";
import { RunConfig } from "@/lib/server/runs";

export async function getSignedObjectUrl(
  run: RunConfig,
  key?: string,
  expiresIn: number = serverEnv.urlExpirySeconds,
) {
  const s3 = new S3Client({ region: run.region });
  const command = new GetObjectCommand({
    Bucket: run.bucket,
    Key: key ?? run.key,
  });
  return getSignedUrl(s3, command, { expiresIn });
}

export async function fetchObjectStream(run: RunConfig, key?: string) {
  const url = await getSignedObjectUrl(run, key);
  const res = await fetchWithTimeout(
    url,
    {},
    serverEnv.fetchTimeoutMs,
    "s3_object",
  );
  if (!res.ok || !res.body) {
    const status = res.status || 502;
    throw new Error(`object_fetch_failed:${status}`);
  }
  return {
    body: res.body,
    contentType: res.headers.get("Content-Type") || "application/jsonl",
  };
}
