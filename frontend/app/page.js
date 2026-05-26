import Link from "next/link";

import AppShell from "../components/AppShell";

export default function Home() {
  return (
    <AppShell>
      <section className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-start">
        <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-8 shadow-2xl shadow-black/20">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-300">
            README for the web app
          </p>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            Generate literature-backed gene annotations without babysitting a terminal.
          </h1>
          <p className="mt-5 text-lg leading-8 text-slate-300">
            The autoannotator takes an organism profile and locus, gathers
            relevant literature, asks the configured model to synthesize an
            annotation, and stores the generated result for review. Runs can
            take a long time, so the web app submits work to a backend queue
            and lets you come back later.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/jobs"
              className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
            >
              Submit a job
            </Link>
            <Link
              href="/annotations"
              className="rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/70"
            >
              Search annotations
            </Link>
          </div>
        </div>

        <aside className="rounded-3xl border border-amber-300/30 bg-amber-300/10 p-6 text-amber-50">
          <h2 className="text-xl font-semibold">Important limitations</h2>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-amber-100/90">
            <li>Only one annotation job runs at a time; new jobs wait in order.</li>
            <li>Real jobs require the same Ollama, model, PubMed, and cache setup as the CLI.</li>
            <li>Generated annotations should be reviewed before being treated as curated truth.</li>
            <li>Progress is intentionally coarse until the annotator pipeline is instrumented in more detail.</li>
          </ul>
        </aside>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-3">
        <div className="rounded-2xl border border-white/10 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold text-white">Inputs</h2>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            A job needs a profile or organism/strain pair plus a locus. A gene
            name can be supplied when you already know the preferred symbol.
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold text-white">Queue</h2>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Submissions are persisted in SQLite. The worker drains queued jobs
            sequentially so heavy annotation runs do not compete with each other.
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold text-white">Results</h2>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Completed jobs are saved to MongoDB by canonical organism profile
            and normalized locus. New runs preserve older versions.
          </p>
        </div>
      </section>
    </AppShell>
  );
}
