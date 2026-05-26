import { Suspense } from "react";

import AppShell from "../../components/AppShell";
import JobWorkspace from "../../components/JobWorkspace";

export const metadata = {
  title: "Jobs · Gene Autoannotator",
};

export default function JobsPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="rounded-3xl border border-white/10 bg-slate-900 p-8 text-slate-300">
            Loading job workspace...
          </div>
        }
      >
        <JobWorkspace />
      </Suspense>
    </AppShell>
  );
}
