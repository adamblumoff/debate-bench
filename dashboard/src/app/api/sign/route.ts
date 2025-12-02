import { NextRequest, NextResponse } from "next/server";
import { serverEnv } from "@/lib/env";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const s3 = new S3Client({ region: serverEnv.region });

export async function GET(req: NextRequest) {
  const key = req.nextUrl.searchParams.get("key") || serverEnv.key;
  if (key !== serverEnv.key) {
    return NextResponse.json({ error: "Key not allowed" }, { status: 400 });
  }
  const expiresIn = serverEnv.urlExpirySeconds;
  const command = new GetObjectCommand({ Bucket: serverEnv.bucket, Key: key });
  const url = await getSignedUrl(s3, command, { expiresIn });
  return NextResponse.json({ url, expiresIn });
}
