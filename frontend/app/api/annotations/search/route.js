import { NextResponse } from "next/server";

import { annotationStoreFromEnv } from "../../../../lib/annotationStore.js";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function parseLimit(value) {
  if (value === null) {
    return 20;
  }

  const limit = Number(value);
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    return null;
  }
  return limit;
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("query") || "";
  const limit = parseLimit(searchParams.get("limit"));

  if (limit === null) {
    return NextResponse.json(
      { detail: "limit must be an integer between 1 and 100" },
      { status: 422 },
    );
  }

  try {
    const matches = await annotationStoreFromEnv().search(query, limit);
    return NextResponse.json({ query, matches });
  } catch (error) {
    return NextResponse.json({ detail: error.message }, { status: 503 });
  }
}
