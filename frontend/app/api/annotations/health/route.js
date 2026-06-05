import { NextResponse } from "next/server";

import { annotationStoreFromEnv } from "../../../../lib/annotationStore.js";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const health = await annotationStoreFromEnv().health();
  return NextResponse.json(health);
}
