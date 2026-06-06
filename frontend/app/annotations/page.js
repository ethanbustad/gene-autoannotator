import { Suspense } from "react";

import AnnotationExplorer from "../../components/AnnotationExplorer";
import AppShell from "../../components/AppShell";
import { searchStoredAnnotations } from "../../lib/annotationStore";
import { getAnnotationsCollection } from "../../lib/mongodb";

export const metadata = {
  title: "Annotations · Gene Autoannotator",
};

async function getInitialMatches(query) {
  if (!query) {
    return { matches: [], message: "" };
  }

  try {
    const collection = await getAnnotationsCollection();
    const matches = await searchStoredAnnotations(collection, query);
    return { matches, message: "" };
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
