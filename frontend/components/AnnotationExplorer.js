"use client";

import { useState } from "react";
import Link from "next/link";

import {
  getAnnotation,
  getAnnotationVersions,
  searchAnnotations,
} from "../lib/api";
import {
  getHiddenMatchCount,
  getVisibleMatches,
} from "../lib/annotationMatches";
import {
  getGeneratedFieldRows,
  getMetadataRows,
  getPmcIdsAnalyzed,
} from "../lib/annotationDisplay";
import { buildJobPrefillHref } from "../lib/form";

function EmptyState({ query }) {
  const href = `/jobs?locus=${encodeURIComponent(query)}`;
  return (
    <div className="workbench-muted-bg rounded-2xl border border-dashed workbench-border p-8 text-center">
      <h2 className="workbench-foreground text-2xl font-bold tracking-[-0.03em]">No annotation found</h2>
      <p className="workbench-muted mx-auto mt-3 max-w-2xl text-sm leading-6">
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
      <div className="workbench-card workbench-muted p-8">
        Select a search result to view the generated annotation.
      </div>
    );
  }

  const generated = annotation.generated_at
    ? new Date(annotation.generated_at).toLocaleString()
    : "Unknown";
  const generatedRows = getGeneratedFieldRows(annotation);
  const metadataRows = getMetadataRows(annotation);
  const pmcIdsAnalyzed = getPmcIdsAnalyzed(annotation);

  // The backend returns the current annotation inline. Older versions are
  // loaded on demand because most review sessions only need the latest result.
  return (
    <article className="workbench-card min-w-0 max-w-full overflow-hidden p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="workbench-kicker">
            Current annotation
          </p>
          <h2 className="workbench-foreground mt-2 text-3xl font-bold tracking-[-0.04em]">
            {annotation.gene_name || annotation.normalized_locus}
          </h2>
          <p className="workbench-muted mt-2 text-sm">
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

      <dl className="mt-6 grid overflow-hidden rounded-xl border workbench-border text-sm sm:grid-cols-3">
        <div className="workbench-muted-bg border-b workbench-border p-4 sm:border-r sm:border-b-0">
          <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">Generated</dt>
          <dd className="mt-1 text-[#3d463f]">{generated}</dd>
        </div>
        <div className="workbench-muted-bg border-b workbench-border p-4 sm:border-r sm:border-b-0">
          <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">Versions</dt>
          <dd className="mt-1 text-[#3d463f]">{annotation.version_count}</dd>
        </div>
        <div className="workbench-muted-bg p-4">
          <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">Job</dt>
          <dd className="mt-1 break-all text-[#3d463f]">{annotation.job_id || "Unknown"}</dd>
        </div>
      </dl>

      <div className="mt-6 grid gap-4">
        <section className="rounded-xl border workbench-border bg-[#fffefa] p-5">
          <h3 className="workbench-foreground text-xl font-bold tracking-[-0.02em]">
            Generated annotation fields
          </h3>
          <dl className="mt-5 grid gap-4">
            {generatedRows.map((row) => (
              <div key={row.key} className="workbench-muted-bg rounded-xl border workbench-border p-4">
                <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">
                  {row.label}
                </dt>
                <dd className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#3d463f]">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <details className="rounded-xl border workbench-border bg-[#fffefa] p-4">
          <summary className="workbench-foreground cursor-pointer text-sm font-bold">
            Annotation metadata
          </summary>
          <dl className="mt-4 grid gap-3 text-sm">
            {metadataRows.map((row) => (
              <div key={row.key} className="workbench-muted-bg rounded-xl border workbench-border p-4">
                <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">
                  {row.label}
                </dt>
                <dd className="mt-2 whitespace-pre-wrap leading-6 text-[#3d463f]">{row.value}</dd>
              </div>
            ))}
          </dl>

          <details className="workbench-muted-bg mt-4 rounded-xl border workbench-border p-4">
            <summary className="workbench-foreground cursor-pointer text-sm font-bold">
              PMC IDs analyzed
            </summary>
            {pmcIdsAnalyzed.length > 0 ? (
              <ul className="mt-3 grid gap-2 text-sm text-[#3d463f] sm:grid-cols-2">
                {pmcIdsAnalyzed.map((pmcId) => (
                  <li key={pmcId} className="rounded-lg bg-white/70 px-3 py-2">
                    PMC{pmcId}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="workbench-muted mt-3 text-sm">No analyzed PMC IDs stored.</p>
            )}
          </details>
        </details>

        <details className="min-w-0 max-w-full overflow-hidden rounded-xl border workbench-border bg-[#fffefa] p-4">
          <summary className="workbench-foreground cursor-pointer text-sm font-bold">
            Raw JSON
          </summary>
          <pre className="annotation-raw-json workbench-muted-bg mt-4 max-h-96 rounded-xl p-4 text-xs leading-5 text-[#3d463f]">
            {JSON.stringify(annotation.result, null, 2)}
          </pre>
        </details>
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
                  className="workbench-muted-bg rounded-xl border workbench-border p-4 text-sm"
                >
                  <p className="workbench-foreground font-bold">
                    {version.gene_name || "Older annotation"}
                  </p>
                  <p className="workbench-muted mt-1">
                    Generated {new Date(version.generated_at).toLocaleString()} · job{" "}
                    {version.job_id}
                  </p>
                </div>
              ))
            ) : (
              <p className="workbench-muted text-sm">No older versions stored yet.</p>
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
  const [showAllMatches, setShowAllMatches] = useState(false);
  const hiddenMatchCount = getHiddenMatchCount(matches);
  const visibleMatches = getVisibleMatches(matches, showAllMatches);

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
    setShowAllMatches(false);

    // Searching returns summaries only. Selecting a match fetches the full
    // current annotation so large JSON payloads are not loaded for every row.
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
        <h1 className="workbench-foreground mt-2 text-3xl font-bold tracking-[-0.04em]">
          Search generated annotations
        </h1>
        <p className="workbench-muted mt-3 max-w-3xl text-sm leading-6">
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
        {message ? <p className="workbench-amber mt-4 text-sm">{message}</p> : null}
      </section>

      <div className="grid items-start gap-5 lg:grid-cols-[0.8fr_1.2fr]">
        <section className="workbench-card p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="workbench-foreground text-2xl font-bold tracking-[-0.03em]">
              Matches
            </h2>
            {hiddenMatchCount > 0 ? (
              <button
                type="button"
                onClick={() => setShowAllMatches((current) => !current)}
                className="workbench-button workbench-button-secondary w-36 shrink-0"
              >
                {showAllMatches ? "Hide all" : `View all (${matches.length})`}
              </button>
            ) : null}
          </div>
          <div className="mt-5 grid gap-3">
            {visibleMatches.map((match) => (
              <button
                type="button"
                key={match.id}
                onClick={() => loadAnnotation(match.id)}
                className="workbench-surface-bg rounded-xl border workbench-border p-4 text-left transition hover:border-[#557864]"
              >
                <p className="workbench-foreground font-bold">
                  {match.gene_name || match.normalized_locus}
                </p>
                <p className="workbench-muted mt-1 text-sm">
                  {match.canonical_name} · {match.normalized_locus}
                </p>
                <p className="workbench-muted mt-2 text-xs">
                  {match.version_count} older version{match.version_count === 1 ? "" : "s"}
                </p>
              </button>
            ))}

            {searchedQuery && matches.length === 0 && !isSearching ? (
              <EmptyState query={searchedQuery} />
            ) : null}

            {!searchedQuery ? (
              <p className="workbench-muted rounded-2xl border border-dashed workbench-border p-6 text-sm">
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
