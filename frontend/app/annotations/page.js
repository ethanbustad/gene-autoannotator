import { Suspense } from "react";

import AnnotationExplorer from "../../components/AnnotationExplorer";
import AppShell from "../../components/AppShell";
import { getApiBaseUrl } from "../../lib/api";

export const metadata = {
  title: "Annotations · Gene Autoannotator",
};

async function getInitialMatches(query) {
  if (!query) {
    return { matches: [], message: "" };
  }

  try {
    const response = await fetch(
      `${getApiBaseUrl()}/annotations/search?query=${encodeURIComponent(query)}`,
      { cache: "no-store" },
    );
    const payload = await response.json();
    if (!response.ok) {
      return {
        matches: [],
        message: payload?.detail || `Backend returned HTTP ${response.status}`,
      };
    }
    return { matches: payload.matches || [], message: "" };
  } catch (error) {
    return { matches: [], message: error.message };
  }
}

export default async function AnnotationsPage({ searchParams }) {
  const params = await searchParams;
  const initialQuery = params?.query || "";
  const initial = await getInitialMatches(initialQuery);

  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="rounded-3xl border border-white/10 bg-slate-900 p-8 text-slate-300">
            Loading annotation search...
          </div>
        }
      >
        <AnnotationExplorer
          initialQuery={initialQuery}
          initialMatches={initial.matches}
          initialMessage={initial.message}
        />
      </Suspense>
    </AppShell>
  );
}
