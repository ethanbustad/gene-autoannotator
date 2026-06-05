import { NextResponse } from "next/server";

import { annotationStoreFromEnv } from "../../../../../lib/annotationStore.js";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(_request, context) {
  const { annotationId } = await context.params;

  try {
    const versions = await annotationStoreFromEnv().getVersions(annotationId);
    if (versions === null) {
      return NextResponse.json({ detail: "Annotation not found" }, { status: 404 });
    }
    return NextResponse.json({ annotation_id: annotationId, versions });
  } catch (error) {
    return NextResponse.json({ detail: error.message }, { status: 503 });
  }
}
