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
  if (status === "completed") return "border-l-[var(--blue)] bg-[var(--surface)]";
  if (status === "failed") return "border-l-[var(--red)] bg-[#fbefed]";
  if (status === "running") return "border-l-[var(--green)] bg-[linear-gradient(90deg,var(--green-soft),var(--surface)_42%)]";
  return "border-l-[#b9ad99] bg-[var(--surface)]";
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
      className={`min-h-32 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4 ${
        ok ? "border-t-[5px] border-t-[var(--green)]" : "border-t-[5px] border-t-[var(--amber)]"
      }`}
    >
      <p className="text-sm font-semibold text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-base font-bold text-[var(--foreground)]">
        {ok ? "Connected" : status || "Unavailable"}
      </p>
      {detail ? <p className="mt-2 text-xs leading-5 text-[var(--muted)]">{detail}</p> : null}
    </div>
  );
}

function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(Number(bytes))) {
    return "unknown";
  }

  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let value = Number(bytes);
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatResourceDetail(resources) {
  if (!resources || resources.status !== "ok") {
    return resources?.message;
  }

  const cpu = `${Math.round(resources.cpu_percent ?? 0)}%`;
  const used = formatBytes(resources.memory_used_bytes);
  const total = formatBytes(resources.memory_total_bytes);
  const available = formatBytes(resources.memory_available_bytes);
  const memoryPercent = Math.round(resources.memory_percent ?? 0);

  return `CPU ${cpu} · RAM ${used} / ${total} used (${memoryPercent}%) · ${available} available`;
}

function JobTile({ job }) {
  const elapsedFrom = job.started_at || job.created_at;
  const elapsed = formatElapsedSeconds(secondsSince(elapsedFrom));
  const request = job.request || {};
  const step = stepLabels[job.current_step] || stepLabels[job.status] || job.status;

  return (
    <article className={`rounded-2xl border border-[var(--line)] border-l-[5px] p-4 ${statusTone(job.status)}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-lg font-bold tracking-[-0.02em] text-[var(--foreground)]">
            {request.name || request.locus || "Unknown locus"}
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {request.profile || request.organism || "default profile"} · {request.locus}
          </p>
        </div>
        <span className="rounded-full border border-[var(--line)] bg-white/60 px-3 py-1 text-xs font-bold uppercase tracking-wide text-[#3f4b43]">
          {job.status}
        </span>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#e3dbcf]">
        <div
          className={`h-full rounded-full ${
            job.status === "failed" ? "bg-[var(--red)]" : "bg-[var(--green)]"
          }`}
          style={{ width: `${progressPercent(job)}%` }}
        />
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div className="border-t border-[var(--line)] pt-2">
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted)]">Step</dt>
          <dd className="mt-1 text-[#3d463f]">{step}</dd>
        </div>
        <div className="border-t border-[var(--line)] pt-2">
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted)]">Queue</dt>
          <dd className="mt-1 text-[#3d463f]">
            {job.queue_position ? `#${job.queue_position}` : "Active or finished"}
          </dd>
        </div>
        <div className="border-t border-[var(--line)] pt-2">
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted)]">Elapsed</dt>
          <dd className="mt-1 text-[#3d463f]">{elapsed}</dd>
        </div>
      </dl>

      {job.error ? <p className="mt-4 text-sm text-[var(--red)]">{job.error}</p> : null}
      {job.annotation_error ? (
        <p className="mt-4 text-sm text-[var(--amber)]">
          Annotation storage warning: {job.annotation_error}
        </p>
      ) : null}

      {job.result_available ? (
        <Link
          href={`/annotations?query=${encodeURIComponent(request.locus || "")}`}
          className="mt-4 inline-flex text-sm font-bold text-[var(--green)] hover:text-[var(--nav)]"
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
    <div className="grid gap-5">
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
        <div className="workbench-card flex min-h-64 flex-col justify-between p-6">
          <div>
            <p className="workbench-kicker">
              Backend
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-[-0.04em] text-[var(--foreground)]">
              Submit and monitor jobs
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--muted)]">
              Choose a configured profile, enter a locus, and add the annotation run to the
              shared queue. Status stays visible beside the instructions so backend or storage
              problems are obvious before submitting work.
            </p>
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                refreshHealth();
                refreshJobs();
              }}
              className="workbench-button workbench-button-secondary"
            >
              Refresh
            </button>
            <span className="workbench-button workbench-button-secondary">
              Queue runs sequentially
            </span>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
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
            detail={formatResourceDetail(health?.resources)}
          />
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="workbench-card p-6">
          <h2 className="text-2xl font-bold tracking-[-0.03em]">New annotation job</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Choose a configured profile, provide the locus, and submit the run.
            Jobs are queued and executed sequentially; a real annotation can take hours.
          </p>

          <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
            <label className="grid gap-2 text-sm font-medium">
              Profile
              <select
                value={form.profile}
                onChange={(event) => updateForm("profile", event.target.value)}
                className="workbench-input"
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
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-muted)] p-4 text-sm text-[var(--muted)]">
                Expected locus format:{" "}
                <code className="rounded bg-[#eee6d9] px-1 py-0.5">
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
                    className="workbench-input"
                    placeholder="Trypanosoma cruzi"
                  />
                </label>
                <label className="grid gap-2 text-sm font-medium">
                  Strain
                  <input
                    value={form.strain}
                    onChange={(event) => updateForm("strain", event.target.value)}
                    className="workbench-input"
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
                className="workbench-input"
                placeholder="Rv0001 or TcCLB.503799.4"
              />
            </label>

            <label className="grid gap-2 text-sm font-medium">
              Optional gene name
              <input
                value={form.name}
                onChange={(event) => updateForm("name", event.target.value)}
                className="workbench-input"
                placeholder="dnaA"
              />
            </label>

            <div className="grid gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-muted)] p-4 text-sm">
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
              <p className="rounded-xl border border-[var(--line)] bg-[var(--amber-soft)] p-4 text-sm text-[#5f4b2e]">
                {statusMessage}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={!canSubmit}
              suppressHydrationWarning
              className="workbench-button workbench-button-primary min-h-11 px-5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Submitting..." : "Queue annotation job"}
            </button>
          </form>
        </section>

        <section className="workbench-card p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-2xl font-bold tracking-[-0.03em] text-[var(--foreground)]">Job queue</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">
                {queue.running || 0} running · {queue.queued || 0} queued ·{" "}
                {queue.completed || 0} completed · {queue.failed || 0} failed
              </p>
            </div>
            <button
              type="button"
              onClick={handleClearHistory}
              disabled={(queue.completed || 0) + (queue.failed || 0) === 0}
              suppressHydrationWarning
              className="workbench-button workbench-button-secondary disabled:cursor-not-allowed disabled:opacity-50"
            >
              Clear finished history
            </button>
          </div>

          <div className="mt-6 grid gap-4">
            {jobs.length > 0 ? (
              jobs.map((job) => <JobTile key={job.id} job={job} />)
            ) : (
              <div className="rounded-2xl border border-dashed border-[var(--line)] p-8 text-center text-[var(--muted)]">
                No jobs have been submitted yet.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
