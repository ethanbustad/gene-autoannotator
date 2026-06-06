import { NextResponse } from "next/server";

import { getNextAnnotationHealth } from "../../../../lib/mongodb";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const health = await getNextAnnotationHealth();
  const status = health.status === "ok" ? 200 : 503;
  return NextResponse.json(health, { status });
}
