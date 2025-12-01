import { serverEnv } from "@/lib/env";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const s3 = new S3Client({ region: serverEnv.region });

export async function GET() {
  const command = new GetObjectCommand({ Bucket: serverEnv.bucket, Key: serverEnv.key });
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
