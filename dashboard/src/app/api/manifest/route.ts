import { NextResponse } from "next/server";
import { serverEnv } from "@/lib/env";

export async function GET() {
  return NextResponse.json({
    runs: [
      {
        id: "default",
        label: "Balanced sample5 (2025-11-30)",
        key: serverEnv.key,
        bucket: serverEnv.bucket,
        region: serverEnv.region,
      },
    ],
  });
}
