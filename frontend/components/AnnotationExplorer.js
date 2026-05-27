"use client";

import { useState } from "react";
import Link from "next/link";

import {
  getAnnotation,
  getAnnotationVersions,
  searchAnnotations,
} from "../lib/api";
import { buildJobPrefillHref } from "../lib/form";

function EmptyState({ query }) {
  const href = `/jobs?locus=${encodeURIComponent(query)}`;
  return (
    <div className="rounded-2xl border border-dashed border-[var(--line)] bg-[var(--surface-muted)] p-8 text-center">
      <h2 className="text-2xl font-bold tracking-[-0.03em] text-[var(--foreground)]">No annotation found</h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-[var(--muted)]">
        There is no stored annotation matching this search yet. You can submit
        the locus as a new queued job and return here after it completes.
      </p>
      <Link
        href={href}
        className="workbench-button workbench-button-primary mt-5"
      >
        Submit this gene for annotation
      </Link>
    </div>
  );
}

function AnnotationDetail({ annotation, versions, onLoadVersions }) {
  if (!annotation) {
    return (
      <div className="workbench-card p-8 text-[var(--muted)]">
        Select a search result to view the generated annotation.
      </div>
    );
  }

  const generated = annotation.generated_at
    ? new Date(annotation.generated_at).toLocaleString()
    : "Unknown";
  const resultAnnotation = annotation.result?.annotation || {};

  return (
    <article className="workbench-card p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="workbench-kicker">
            Current annotation
          </p>
          <h2 className="mt-2 text-3xl font-bold tracking-[-0.04em] text-[var(--foreground)]">
            {annotation.gene_name || annotation.normalized_locus}
          </h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            {annotation.canonical_name} · {annotation.normalized_locus}
          </p>
        </div>
        <Link
          href={buildJobPrefillHref(annotation)}
          className="workbench-button workbench-button-secondary"
        >
          Update annotation
        </Link>
      </div>

      <dl className="mt-6 grid overflow-hidden rounded-xl border border-[var(--line)] text-sm sm:grid-cols-3">
        <div className="border-b border-[var(--line)] bg-[var(--surface-muted)] p-4 sm:border-r sm:border-b-0">
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted)]">Generated</dt>
          <dd className="mt-1 text-[#3d463f]">{generated}</dd>
        </div>
        <div className="border-b border-[var(--line)] bg-[var(--surface-muted)] p-4 sm:border-r sm:border-b-0">
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted)]">Versions</dt>
          <dd className="mt-1 text-[#3d463f]">{annotation.version_count}</dd>
        </div>
        <div className="bg-[var(--surface-muted)] p-4">
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted)]">Job</dt>
          <dd className="mt-1 break-all text-[#3d463f]">{annotation.job_id || "Unknown"}</dd>
        </div>
      </dl>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-[var(--line)] bg-[#fffefa] p-4">
          <h3 className="font-bold text-[var(--foreground)]">Generated fields</h3>
          <dl className="mt-4 space-y-3 text-sm">
            {Object.entries(resultAnnotation)
              .filter(([key]) => key !== "annotation_metadata")
              .slice(0, 8)
              .map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted)]">{key.replaceAll("_", " ")}</dt>
                  <dd className="mt-1 text-[#3d463f]">
                    {Array.isArray(value) ? value.join(", ") : String(value ?? "Not provided")}
                  </dd>
                </div>
              ))}
          </dl>
        </section>

        <section className="rounded-xl border border-[var(--line)] bg-[#fffefa] p-4">
          <h3 className="font-bold text-[var(--foreground)]">Raw result preview</h3>
          <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-[var(--surface-muted)] p-4 text-xs leading-5 text-[#3d463f]">
            {JSON.stringify(annotation.result, null, 2)}
          </pre>
        </section>
      </div>

      <div className="mt-6">
        <button
          type="button"
          onClick={onLoadVersions}
          className="workbench-button workbench-button-secondary"
        >
          {versions ? "Refresh older versions" : "Show older versions"}
        </button>

        {versions ? (
          <div className="mt-4 grid gap-3">
            {versions.length > 0 ? (
              versions.map((version) => (
                <div
                  key={version.version_id}
                  className="rounded-xl border border-[var(--line)] bg-[var(--surface-muted)] p-4 text-sm"
                >
                  <p className="font-bold text-[var(--foreground)]">
                    {version.gene_name || "Older annotation"}
                  </p>
                  <p className="mt-1 text-[var(--muted)]">
                    Generated {new Date(version.generated_at).toLocaleString()} · job{" "}
                    {version.job_id}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-[var(--muted)]">No older versions stored yet.</p>
            )}
          </div>
        ) : null}
      </div>
    </article>
  );
}

export default function AnnotationExplorer({
  initialQuery = "",
  initialMatches = [],
  initialMessage = "",
}) {
  const [query, setQuery] = useState(initialQuery);
  const [matches, setMatches] = useState(initialMatches);
  const [selected, setSelected] = useState(null);
  const [versions, setVersions] = useState(null);
  const [message, setMessage] = useState(initialMessage);
  const [searchedQuery, setSearchedQuery] = useState(initialQuery);
  const [isSearching, setIsSearching] = useState(false);

  async function runSearch(nextQuery = query) {
    const trimmed = nextQuery.trim();
    if (!trimmed) {
      setMessage("Enter a locus, gene name, or organism-related term.");
      return;
    }

    setIsSearching(true);
    setMessage("");
    setSelected(null);
    setVersions(null);
    setSearchedQuery(trimmed);

    try {
      const payload = await searchAnnotations(trimmed);
      setMatches(payload.matches || []);
    } catch (error) {
      setMatches([]);
      setMessage(error.message);
    } finally {
      setIsSearching(false);
    }
  }

  async function loadAnnotation(annotationId) {
    setMessage("");
    setVersions(null);
    try {
      setSelected(await getAnnotation(annotationId));
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function loadVersions() {
    if (!selected) return;
    try {
      const payload = await getAnnotationVersions(selected.id);
      setVersions(payload.versions || []);
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <div className="grid gap-5">
      <section className="workbench-card p-6">
        <p className="workbench-kicker">
          Annotation library
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-[-0.04em] text-[var(--foreground)]">
          Search generated annotations
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">
          Search by locus, gene name, profile, or terms present in stored
          annotation metadata. Current annotations are shown first; older
          versions stay hidden until requested.
        </p>

        <form
          className="mt-6 flex flex-col gap-3 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            runSearch();
          }}
        >
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="workbench-input min-w-0 flex-1"
            placeholder="Rv0001, dnaA, TcCLB.503799.4..."
          />
          <button
            type="submit"
            disabled={isSearching}
            className="workbench-button workbench-button-primary min-h-11 px-5 disabled:opacity-60"
          >
            {isSearching ? "Searching..." : "Search"}
          </button>
        </form>
        {message ? <p className="mt-4 text-sm text-[var(--amber)]">{message}</p> : null}
      </section>

      <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
        <section className="workbench-card p-6">
          <h2 className="text-2xl font-bold tracking-[-0.03em] text-[var(--foreground)]">Matches</h2>
          <div className="mt-5 grid gap-3">
            {matches.map((match) => (
              <button
                type="button"
                key={match.id}
                onClick={() => loadAnnotation(match.id)}
                className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4 text-left transition hover:border-[var(--green)]"
              >
                <p className="font-bold text-[var(--foreground)]">
                  {match.gene_name || match.normalized_locus}
                </p>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  {match.canonical_name} · {match.normalized_locus}
                </p>
                <p className="mt-2 text-xs text-[var(--muted)]">
                  {match.version_count} older version{match.version_count === 1 ? "" : "s"}
                </p>
              </button>
            ))}

            {searchedQuery && matches.length === 0 && !isSearching ? (
              <EmptyState query={searchedQuery} />
            ) : null}

            {!searchedQuery ? (
              <p className="rounded-2xl border border-dashed border-[var(--line)] p-6 text-sm text-[var(--muted)]">
                Search for an annotation to get started.
              </p>
            ) : null}
          </div>
        </section>

        <AnnotationDetail
          annotation={selected}
          versions={versions}
          onLoadVersions={loadVersions}
        />
      </div>
    </div>
  );
}
