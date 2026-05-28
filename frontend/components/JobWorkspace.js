"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";

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
  formatJobElapsed,
} from "../lib/form";
import { getHiddenJobCount, getVisibleJobs, shouldShowRunningSpinner } from "../lib/jobQueue";

const stepLabels = {
  queued: "Waiting in queue",
  running: "Annotator running",
  saving_result: "Saving result",
  completed: "Completed",
  failed: "Failed",
};

function statusTone(status) {
  if (status === "completed") return "job-card-completed";
  if (status === "failed") return "job-card-failed";
  if (status === "running") return "job-card-running";
  return "job-card-queued";
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
      className={`workbench-surface-bg min-h-32 rounded-2xl border workbench-border p-4 ${
        ok ? "health-status-ok" : "health-status-warn"
      }`}
    >
      <p className="workbench-muted text-sm font-semibold">{label}</p>
      <p className="workbench-foreground mt-2 text-base font-bold">
        {ok ? "Connected" : status || "Unavailable"}
      </p>
      {detail ? <p className="workbench-muted mt-2 text-xs leading-5">{detail}</p> : null}
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
  const elapsed = formatJobElapsed(job);
  const request = job.request || {};
  const step = stepLabels[job.current_step] || stepLabels[job.status] || job.status;
  const showSpinner = shouldShowRunningSpinner(job);

  return (
    <article className={`rounded-2xl border workbench-border border-l-[5px] p-4 ${statusTone(job.status)}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="workbench-foreground text-lg font-bold tracking-[-0.02em]">
            {request.name || request.locus || "Unknown locus"}
          </p>
          <p className="workbench-muted mt-1 text-sm">
            {request.profile || request.organism || "default profile"} · {request.locus}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {showSpinner ? (
            <motion.span
              aria-label="Annotation job running"
              className="inline-block size-4 rounded-full border-2 border-[#b8c7bb] border-t-[#557864]"
              animate={{ rotate: 360 }}
              transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
            />
          ) : null}
          <span className="rounded-full border workbench-border bg-white/60 px-3 py-1 text-xs font-bold uppercase tracking-wide text-[#3f4b43]">
            {job.status}
          </span>
        </div>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#e3dbcf]">
        <div
          className={`h-full rounded-full ${
            job.status === "failed" ? "bg-[#994f56]" : "bg-[#557864]"
          }`}
          style={{ width: `${progressPercent(job)}%` }}
        />
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div className="border-t workbench-border pt-2">
          <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">Step</dt>
          <dd className="mt-1 text-[#3d463f]">{step}</dd>
        </div>
        <div className="border-t workbench-border pt-2">
          <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">Queue</dt>
          <dd className="mt-1 text-[#3d463f]">
            {job.queue_position ? `#${job.queue_position}` : "Active or finished"}
          </dd>
        </div>
        <div className="border-t workbench-border pt-2">
          <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">Elapsed</dt>
          <dd className="mt-1 text-[#3d463f]">{elapsed}</dd>
        </div>
      </dl>

      {job.error ? <p className="workbench-red mt-4 text-sm">{job.error}</p> : null}
      {job.annotation_error ? (
        <p className="workbench-amber mt-4 text-sm">
          Annotation storage warning: {job.annotation_error}
        </p>
      ) : null}

      {job.result_available ? (
        <Link
          href={`/annotations?query=${encodeURIComponent(request.locus || "")}`}
          className="workbench-green mt-4 inline-flex text-sm font-bold hover:text-[#111a16]"
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
  const [showAllJobs, setShowAllJobs] = useState(false);
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
  const hiddenJobCount = getHiddenJobCount(jobs);
  const visibleJobs = getVisibleJobs(jobs, showAllJobs);

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
            <h1 className="workbench-foreground mt-2 text-3xl font-bold tracking-[-0.04em]">
              Submit and monitor jobs
            </h1>
            <p className="workbench-muted mt-3 max-w-2xl text-sm leading-6">
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

      <div className="grid items-start gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="workbench-card p-6">
          <h2 className="text-2xl font-bold tracking-[-0.03em]">New annotation job</h2>
          <p className="workbench-muted mt-3 text-sm leading-6">
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
              <div className="workbench-muted-bg workbench-muted rounded-xl border workbench-border p-4 text-sm">
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

            <div className="workbench-muted-bg grid gap-3 rounded-xl border workbench-border p-4 text-sm">
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
              <p className="workbench-amber-bg rounded-xl border workbench-border p-4 text-sm text-[#5f4b2e]">
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
              <h2 className="workbench-foreground text-2xl font-bold tracking-[-0.03em]">Job queue</h2>
              <p className="workbench-muted w-full md:w-35 mt-2 text-sm">
                {queue.running || 0} running · {queue.queued || 0} queued ·{" "}
                {queue.completed || 0} completed · {queue.failed || 0} failed
              </p>
            </div>
            <div className="flex flex-row flex-nowrap items-center gap-2 sm:justify-end">
              {hiddenJobCount > 0 ? (
                <button
                  type="button"
                  onClick={() => setShowAllJobs((current) => !current)}
                  className="workbench-button workbench-button-secondary w-52 shrink-0"
                >
                  {showAllJobs ? "Hide extra jobs" : `Show all jobs (${hiddenJobCount} more)`}
                </button>
              ) : null}
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
          </div>

          <div className="mt-6 grid gap-4">
            {jobs.length > 0 ? (
              visibleJobs.map((job) => <JobTile key={job.id} job={job} />)
            ) : (
              <div className="workbench-muted rounded-2xl border border-dashed workbench-border p-8 text-center">
                No jobs have been submitted yet.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
