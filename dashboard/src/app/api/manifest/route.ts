import { NextResponse } from "next/server";
import { getRuns } from "@/lib/server/runs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const refresh = new URL(request.url).searchParams.get("refresh") === "1";
  const payload = await getRuns(refresh);
  return NextResponse.json(payload);
}
