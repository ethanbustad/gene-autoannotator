async function getBackendHealth() {
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return {
        apiBaseUrl,
        available: false,
        message: `Backend returned HTTP ${response.status}`,
      };
    }

    const payload = await response.json();
    return {
      apiBaseUrl,
      available: payload.status === "ok",
      message: payload.status === "ok" ? "Backend is reachable" : "Unknown status",
    };
  } catch (error) {
    return {
      apiBaseUrl,
      available: false,
      message: error.message,
    };
  }
}

export default async function Home() {
  const health = await getBackendHealth();

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
      <section className="mx-auto flex max-w-5xl flex-col gap-8">
        <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-8 shadow-2xl shadow-black/20">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-300">
            Gene Autoannotator
          </p>
          <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            Browser placeholder for long-running gene annotation jobs
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">
            This page proves the Next.js frontend can talk to the Python API.
            Full job submission, progress, and result pages can build on this
            foundation.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-semibold text-white">Backend Status</h2>
            <div
              className={`mt-4 rounded-xl border p-4 ${
                health.available
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-100"
                  : "border-amber-500/40 bg-amber-500/10 text-amber-100"
              }`}
            >
              <p className="font-medium">
                {health.available ? "Connected" : "Unavailable"}
              </p>
              <p className="mt-2 text-sm opacity-90">{health.message}</p>
            </div>
            <p className="mt-4 break-all text-sm text-slate-400">
              API base URL: {health.apiBaseUrl}
            </p>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-white p-6 text-slate-950">
            <h2 className="text-xl font-semibold">Annotation Request</h2>
            <p className="mt-2 text-sm text-slate-600">
              Placeholder form only. The next frontend phase will submit this
              to <code className="font-mono">POST /jobs</code> and poll job
              status.
            </p>

            <form className="mt-6 grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2 text-sm font-medium">
                Profile
                <input
                  className="rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="tcruzi-clbrener"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-medium">
                Organism
                <input
                  className="rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="Trypanosoma cruzi"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-medium">
                Strain
                <input
                  className="rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="CL Brener"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-medium">
                Locus
                <input
                  className="rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="TcCLB.503799.4"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-medium sm:col-span-2">
                Gene name
                <input
                  className="rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="Optional curated gene name"
                />
              </label>
              <button
                className="rounded-lg bg-slate-950 px-4 py-3 font-semibold text-white opacity-60 sm:col-span-2"
                disabled
              >
                Job submission coming next
              </button>
            </form>
          </section>
        </div>
      </section>
    </main>
  );
}
