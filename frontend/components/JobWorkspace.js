"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import {
  clearFinishedJobHistory,
  createJob,
  getHealth,
  getProfiles,
  listJobs,
  validateJob,
} from "../lib/api";
import {
  buildJobPayload,
  formatElapsedSeconds,
  secondsSince,
} from "../lib/form";

const stepLabels = {
  queued: "Waiting in queue",
  running: "Annotator running",
  saving_result: "Saving result",
  completed: "Completed",
  failed: "Failed",
};

function statusTone(status) {
  if (status === "completed") return "border-emerald-400/40 bg-emerald-400/10";
  if (status === "failed") return "border-rose-400/40 bg-rose-400/10";
  if (status === "running") return "border-cyan-400/40 bg-cyan-400/10";
  return "border-slate-700 bg-slate-900";
}

function progressPercent(job) {
  if (job.status === "completed") return 100;
  if (job.status === "failed") return 100;
  if (job.current_step === "saving_result") return 85;
  if (job.status === "running") return 55;
  return 12;
}

function HealthBadge({ label, status, detail }) {
  const ok = status === "ok";
  return (
    <div
      className={`rounded-2xl border p-4 ${
        ok ? "border-emerald-400/30 bg-emerald-400/10" : "border-amber-400/30 bg-amber-400/10"
      }`}
    >
      <p className="text-sm font-semibold text-white">{label}</p>
      <p className={ok ? "mt-1 text-sm text-emerald-200" : "mt-1 text-sm text-amber-200"}>
        {ok ? "Connected" : status || "Unavailable"}
      </p>
      {detail ? <p className="mt-2 text-xs text-slate-400">{detail}</p> : null}
    </div>
  );
}

function JobTile({ job }) {
  const elapsedFrom = job.started_at || job.created_at;
  const elapsed = formatElapsedSeconds(secondsSince(elapsedFrom));
  const request = job.request || {};
  const step = stepLabels[job.current_step] || stepLabels[job.status] || job.status;

  return (
    <article className={`rounded-2xl border p-5 ${statusTone(job.status)}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-lg font-semibold text-white">
            {request.name || request.locus || "Unknown locus"}
          </p>
          <p className="mt-1 text-sm text-slate-300">
            {request.profile || request.organism || "default profile"} · {request.locus}
          </p>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-200">
          {job.status}
        </span>
      </div>

      <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full ${
            job.status === "failed" ? "bg-rose-400" : "bg-cyan-300"
          }`}
          style={{ width: `${progressPercent(job)}%` }}
        />
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-slate-500">Step</dt>
          <dd className="mt-1 text-slate-200">{step}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Queue</dt>
          <dd className="mt-1 text-slate-200">
            {job.queue_position ? `#${job.queue_position}` : "Active or finished"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Elapsed</dt>
          <dd className="mt-1 text-slate-200">{elapsed}</dd>
        </div>
      </dl>

      {job.error ? <p className="mt-4 text-sm text-rose-200">{job.error}</p> : null}
      {job.annotation_error ? (
        <p className="mt-4 text-sm text-amber-200">
          Annotation storage warning: {job.annotation_error}
        </p>
      ) : null}

      {job.result_available ? (
        <Link
          href={`/annotations?query=${encodeURIComponent(request.locus || "")}`}
          className="mt-4 inline-flex text-sm font-semibold text-cyan-200 hover:text-cyan-100"
        >
          Search stored annotation
        </Link>
      ) : null}
    </article>
  );
}

export default function JobWorkspace() {
  const searchParams = useSearchParams();
  const [health, setHealth] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [queue, setQueue] = useState({ queued: 0, running: 0, completed: 0, failed: 0 });
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState({
    profile: searchParams.get("profile") || "mtb-h37rv",
    organism: "",
    strain: "",
    locus: searchParams.get("locus") || "",
    name: searchParams.get("name") || "",
    allowOnlineNameLookup: true,
    refreshGeneNameCache: false,
    cacheSuppliedName: false,
  });

  const apiAvailable = health?.status === "ok";
  const canSubmit = health !== null && apiAvailable && !isSubmitting;

  async function refreshHealth() {
    try {
      setHealth(await getHealth());
    } catch (error) {
      setHealth({
        status: "offline",
        stores: {},
        resources: { status: "unavailable", message: error.message },
      });
    }
  }

  async function refreshJobs() {
    try {
      const payload = await listJobs("queue");
      setJobs(payload.jobs || []);
      setQueue(payload.queue || {});
    } catch (error) {
      setStatusMessage(error.message);
    }
  }

  useEffect(() => {
    async function loadInitialData() {
      await refreshHealth();
      try {
        const payload = await getProfiles();
        setProfiles(payload.profiles || []);
      } catch (error) {
        setStatusMessage(error.message);
      }
      await refreshJobs();
    }

    loadInitialData();
    const jobsTimer = window.setInterval(refreshJobs, 5000);
    const healthTimer = window.setInterval(refreshHealth, 15000);
    return () => {
      window.clearInterval(jobsTimer);
      window.clearInterval(healthTimer);
    };
  }, []);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.profile_id === form.profile),
    [profiles, form.profile],
  );

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setStatusMessage("");
    setIsSubmitting(true);

    try {
      const payload = buildJobPayload(form);
      if (!payload.locus) {
        throw new Error("Locus is required.");
      }
      const validation = await validateJob(payload);
      if (!validation.valid) {
        throw new Error(validation.reason || "The locus did not validate for this profile.");
      }
      const created = await createJob(payload);
      setStatusMessage(`Queued job ${created.job_id}. It will run when earlier jobs finish.`);
      await refreshJobs();
    } catch (error) {
      setStatusMessage(error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleClearHistory() {
    const confirmed = window.confirm(
      "Clear completed and failed jobs from the history? Queued and running jobs will stay.",
    );
    if (!confirmed) {
      return;
    }

    try {
      const result = await clearFinishedJobHistory();
      setStatusMessage(`Cleared ${result.deleted} finished job${result.deleted === 1 ? "" : "s"}.`);
      await refreshJobs();
    } catch (error) {
      setStatusMessage(error.message);
    }
  }

  return (
    <div className="grid gap-8">
      <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-300">
              Backend
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-white">Submit and monitor jobs</h1>
          </div>
          <button
            type="button"
            onClick={() => {
              refreshHealth();
              refreshJobs();
            }}
            className="rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-slate-100 hover:border-cyan-300/70"
          >
            Refresh
          </button>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-4">
          <HealthBadge
            label="API"
            status={health?.status}
            detail={apiAvailable ? "FastAPI reachable" : health?.resources?.message}
          />
          <HealthBadge
            label="Job store"
            status={health?.stores?.jobs?.status}
            detail={health?.stores?.jobs?.path}
          />
          <HealthBadge
            label="Annotations"
            status={health?.stores?.annotations?.status}
            detail={health?.stores?.annotations?.message}
          />
          <HealthBadge
            label="Resources"
            status={health?.resources?.status}
            detail={
              health?.resources?.process_memory_mb
                ? `${health.resources.process_memory_mb} MB RSS`
                : health?.resources?.message
            }
          />
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="rounded-3xl border border-white/10 bg-white p-6 text-slate-950">
          <h2 className="text-2xl font-semibold">New annotation job</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Choose a configured profile, provide the locus, and submit the run.
            Jobs are queued and executed sequentially; a real annotation can take hours.
          </p>

          <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
            <label className="grid gap-2 text-sm font-medium">
              Profile
              <select
                value={form.profile}
                onChange={(event) => updateForm("profile", event.target.value)}
                className="rounded-xl border border-slate-300 px-3 py-3"
              >
                <option value="">Custom organism/strain</option>
                {profiles.map((profile) => (
                  <option key={profile.profile_id} value={profile.profile_id}>
                    {profile.canonical_name}
                  </option>
                ))}
              </select>
            </label>

            {selectedProfile ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                Expected locus format:{" "}
                <code className="rounded bg-slate-200 px-1 py-0.5">
                  {selectedProfile.locus_regex}
                </code>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="grid gap-2 text-sm font-medium">
                  Organism
                  <input
                    value={form.organism}
                    onChange={(event) => updateForm("organism", event.target.value)}
                    className="rounded-xl border border-slate-300 px-3 py-3"
                    placeholder="Trypanosoma cruzi"
                  />
                </label>
                <label className="grid gap-2 text-sm font-medium">
                  Strain
                  <input
                    value={form.strain}
                    onChange={(event) => updateForm("strain", event.target.value)}
                    className="rounded-xl border border-slate-300 px-3 py-3"
                    placeholder="CL Brener"
                  />
                </label>
              </div>
            )}

            <label className="grid gap-2 text-sm font-medium">
              Locus
              <input
                value={form.locus}
                onChange={(event) => updateForm("locus", event.target.value)}
                className="rounded-xl border border-slate-300 px-3 py-3"
                placeholder="Rv0001 or TcCLB.503799.4"
              />
            </label>

            <label className="grid gap-2 text-sm font-medium">
              Optional gene name
              <input
                value={form.name}
                onChange={(event) => updateForm("name", event.target.value)}
                className="rounded-xl border border-slate-300 px-3 py-3"
                placeholder="dnaA"
              />
            </label>

            <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={form.allowOnlineNameLookup}
                  onChange={(event) => updateForm("allowOnlineNameLookup", event.target.checked)}
                />
                Allow online gene-name lookup
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={form.refreshGeneNameCache}
                  onChange={(event) => updateForm("refreshGeneNameCache", event.target.checked)}
                />
                Refresh gene-name cache
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={form.cacheSuppliedName}
                  onChange={(event) => updateForm("cacheSuppliedName", event.target.checked)}
                />
                Cache supplied gene name
              </label>
            </div>

            {statusMessage ? (
              <p className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
                {statusMessage}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={!canSubmit}
              suppressHydrationWarning
              className="rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Submitting..." : "Queue annotation job"}
            </button>
          </form>
        </section>

        <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-2xl font-semibold text-white">Job queue</h2>
              <p className="mt-2 text-sm text-slate-400">
                {queue.running || 0} running · {queue.queued || 0} queued ·{" "}
                {queue.completed || 0} completed · {queue.failed || 0} failed
              </p>
            </div>
            <button
              type="button"
              onClick={handleClearHistory}
              disabled={(queue.completed || 0) + (queue.failed || 0) === 0}
              suppressHydrationWarning
              className="rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-slate-100 hover:border-cyan-300/70 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Clear finished history
            </button>
          </div>

          <div className="mt-6 grid gap-4">
            {jobs.length > 0 ? (
              jobs.map((job) => <JobTile key={job.id} job={job} />)
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 p-8 text-center text-slate-400">
                No jobs have been submitted yet.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
