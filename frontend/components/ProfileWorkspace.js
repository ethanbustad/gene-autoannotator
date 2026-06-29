"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  createProfile,
  deleteProfile,
  getProfiles,
  updateProfile,
} from "../lib/api";
import {
  filterProfiles,
  groupProfilesBySpecies,
  PROFILE_SOURCE_FILTERS,
} from "../lib/profileFilters";
import { buildProfilePayload, profileToForm } from "../lib/profileStore";
import CustomFieldsEditor from "./CustomFieldsEditor";
import RegexHelper from "./RegexHelper";

const emptyForm = {
  profileId: "",
  canonicalName: "",
  speciesName: "",
  strain: "",
  synonyms: "",
  speciesSynonyms: "",
  strainSynonyms: "",
  locusRegex: "",
  searchTerms: "",
  targetPatterns: "",
  offTargetPatterns: "",
  excludedSpeciesPatterns: "",
  keggOrganismCode: "",
  customFields: [],
};

const textFields = [
  {
    name: "profileId",
    label: "Profile ID",
    placeholder: "custom-organism",
    required: true,
  },
  {
    name: "canonicalName",
    label: "Canonical name",
    placeholder: "Custom organism strain",
    required: true,
  },
  {
    name: "speciesName",
    label: "Species name",
    placeholder: "Custom organism",
    required: true,
  },
  {
    name: "strain",
    label: "Strain",
    placeholder: "Lab strain or isolate",
  },
  {
    name: "locusRegex",
    label: "Locus regex",
    placeholder: "^CUS_\\d+$",
  },
];

const listFields = [
  {
    name: "synonyms",
    label: "Profile synonyms",
    placeholder: "One profile synonym per line",
  },
  {
    name: "speciesSynonyms",
    label: "Species synonyms",
    placeholder: "One species synonym per line",
  },
  {
    name: "strainSynonyms",
    label: "Strain synonyms",
    placeholder: "One strain synonym per line",
  },
  {
    name: "searchTerms",
    label: "Search terms",
    placeholder: "One literature search term per line",
  },
  {
    name: "targetPatterns",
    label: "Target organism patterns",
    placeholder: "One accepted organism pattern per line",
  },
  {
    name: "offTargetPatterns",
    label: "Off-target patterns",
    placeholder: "One off-target pattern per line",
  },
  {
    name: "excludedSpeciesPatterns",
    label: "Excluded species patterns",
    placeholder: "One excluded species pattern per line",
  },
];

function listToText(values) {
  return (values || []).join("\n");
}

function ProfileDetailList({ profile }) {
  const rows = [
    ["Species", profile.species_name],
    ["Strain", profile.strain],
    ["Profile synonyms", profile.synonyms?.join(", ")],
    ["Species synonyms", profile.species_synonyms?.join(", ")],
    ["Strain synonyms", profile.strain_synonyms?.join(", ")],
    ["Locus regex", profile.locus_regex],
    ["Search terms", profile.search_terms?.join(", ")],
    ["Target patterns", profile.target_patterns?.join(", ")],
    ["Off-target patterns", profile.off_target_patterns?.join(", ")],
    ["Excluded species", profile.excluded_species_patterns?.join(", ")],
    ["KEGG organism code", profile.kegg_organism_code],
    [
      "Custom fields",
      (profile.custom_fields || profile.annotation_fields || [])
        .map((field) => field.key)
        .join(", ") || null,
    ],
  ].filter(([, value]) => value);

  if (rows.length === 0) {
    return null;
  }

  return (
    <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="border-t workbench-border pt-2">
          <dt className="workbench-muted text-xs font-bold uppercase tracking-[0.1em]">
            {label}
          </dt>
          <dd className="mt-1 text-[#3d463f]">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function ProfileWorkspace() {
  const [profiles, setProfiles] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingProfileId, setEditingProfileId] = useState("");
  const [expandedProfileId, setExpandedProfileId] = useState("");
  const [profileQuery, setProfileQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState(PROFILE_SOURCE_FILTERS.ALL);
  const [statusMessage, setStatusMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const formRef = useRef(null);

  const visibleProfiles = useMemo(
    () => filterProfiles(profiles, { query: profileQuery, sourceFilter }),
    [profiles, profileQuery, sourceFilter],
  );
  const profileGroups = useMemo(
    () => groupProfilesBySpecies(visibleProfiles),
    [visibleProfiles],
  );

  async function refreshProfiles() {
    const payload = await getProfiles();
    setProfiles(payload.profiles || []);
  }

  useEffect(() => {
    async function loadProfiles() {
      setIsLoading(true);
      setStatusMessage("");
      try {
        await refreshProfiles();
      } catch (error) {
        setStatusMessage(error.message);
      } finally {
        setIsLoading(false);
      }
    }

    loadProfiles();
  }, []);

  function updateForm(field, value) {
    setForm((current) => {
      const next = { ...current, [field]: value };
      if (field === "keggOrganismCode" && !String(value || "").trim()) {
        next.customFields = (current.customFields || []).map((item) => ({
          ...item,
          ortholog_allowed: false,
        }));
      }
      return next;
    });
  }

  function resetForm() {
    setForm(emptyForm);
    setEditingProfileId("");
    setStatusMessage("");
  }

  function startEditing(profile) {
    if (profile.read_only) {
      return;
    }
    setForm(profileToForm(profile));
    setEditingProfileId(profile.profile_id);
    setExpandedProfileId(profile.profile_id);
    setStatusMessage(`Editing ${profile.profile_id}.`);
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setStatusMessage("");
    setIsSaving(true);

    try {
      const payload = buildProfilePayload(form);
      let successMessage;
      if (editingProfileId) {
        await updateProfile(editingProfileId, payload);
        successMessage = `Updated profile ${editingProfileId}.`;
      } else {
        await createProfile(payload);
        successMessage = `Created profile ${payload.profile_id}.`;
      }
      await refreshProfiles();
      resetForm();
      setStatusMessage(successMessage);
    } catch (error) {
      setStatusMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(profileId) {
    const profile = profiles.find((item) => item.profile_id === profileId);
    if (!profile || profile.read_only) {
      return;
    }

    const confirmed = window.confirm(`Delete user profile ${profileId}?`);
    if (!confirmed) {
      return;
    }

    setStatusMessage("");
    try {
      await deleteProfile(profileId);
      if (editingProfileId === profileId) {
        resetForm();
      }
      await refreshProfiles();
      setStatusMessage(`Deleted profile ${profileId}.`);
    } catch (error) {
      setStatusMessage(error.message);
    }
  }

  return (
    <div className="grid gap-5">
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.95fr)]">
        <div className="workbench-card p-6">
          <p className="workbench-kicker">Organism Profiles</p>
          <h1 className="workbench-foreground mt-2 text-3xl font-bold tracking-[-0.04em]">
            Manage reusable annotation targets
          </h1>
          <p className="workbench-muted mt-3 max-w-2xl text-sm leading-6">
            Built-in profiles are listed for reference. User profiles can be
            added, edited, and removed so job submissions reuse the same
            validation patterns and literature search terms.
          </p>
        </div>

        <div className="workbench-amber-bg workbench-foreground rounded-[18px] border workbench-border p-6">
          <h2 className="text-xl font-bold tracking-[-0.02em]">
            Profile storage
          </h2>
          <p className="mt-3 text-sm leading-6 text-[#5f4b2e]">
            User profile changes are stored by the backend profile API. If MongoDB
            profile storage is not configured, built-in profiles remain visible
            and save/delete actions will report the backend error.
          </p>
        </div>
      </section>

      <div className="grid items-start gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <section ref={formRef} className="workbench-card p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="workbench-foreground text-2xl font-bold tracking-[-0.03em]">
                {editingProfileId ? "Edit user profile" : "New user profile"}
              </h2>
              <p className="workbench-muted mt-2 text-sm leading-6">
                Use one value per line for synonyms, search terms, and organism
                pattern lists.
              </p>
            </div>
            {editingProfileId ? (
              <button
                type="button"
                onClick={resetForm}
                className="workbench-button workbench-button-secondary"
              >
                Cancel edit
              </button>
            ) : null}
          </div>

          <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              {textFields.map((field) => (
                <label key={field.name} className="grid gap-2 text-sm font-medium">
                  {field.label}
                  <input
                    value={form[field.name]}
                    onChange={(event) => updateForm(field.name, event.target.value)}
                    className="workbench-input"
                    placeholder={field.placeholder}
                    required={field.required}
                    disabled={field.name === "profileId" && Boolean(editingProfileId)}
                  />
                </label>
              ))}
            </div>

            <RegexHelper onApply={(regex) => updateForm("locusRegex", regex)} />

            <label className="grid gap-2 text-sm font-medium">
              KEGG organism code (optional)
              <input
                value={form.keggOrganismCode}
                onChange={(event) => updateForm("keggOrganismCode", event.target.value)}
                className="workbench-input"
                placeholder="e.g. mtu, msm, tcr"
              />
              <span className="workbench-muted text-xs font-normal leading-5">
                Required for ortholog lookup. Annotation jobs work without it; ortholog
                fallback and per-field ortholog allowance stay disabled until a code is set.
              </span>
            </label>

            <CustomFieldsEditor
              customFields={form.customFields}
              keggOrganismCode={form.keggOrganismCode}
              onChange={(customFields) => updateForm("customFields", customFields)}
            />

            <div className="grid gap-4 sm:grid-cols-2">
              {listFields.map((field) => (
                <label key={field.name} className="grid gap-2 text-sm font-medium">
                  {field.label}
                  <textarea
                    value={form[field.name]}
                    onChange={(event) => updateForm(field.name, event.target.value)}
                    className="workbench-input min-h-28"
                    placeholder={field.placeholder}
                  />
                </label>
              ))}
            </div>

            {statusMessage ? (
              <p className="workbench-amber-bg rounded-xl border workbench-border p-4 text-sm text-[#5f4b2e]">
                {statusMessage}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={isSaving || isLoading}
              className="workbench-button workbench-button-primary min-h-11 px-5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSaving
                ? "Saving..."
                : editingProfileId
                  ? "Update profile"
                  : "Create profile"}
            </button>
          </form>
        </section>

        <section className="workbench-card p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="workbench-foreground text-2xl font-bold tracking-[-0.03em]">
                Available profiles
              </h2>
              <p className="workbench-muted mt-2 text-sm">
                {visibleProfiles.length} of {profiles.length} profile{profiles.length === 1 ? "" : "s"} shown
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setIsLoading(true);
                refreshProfiles()
                  .catch((error) => setStatusMessage(error.message))
                  .finally(() => setIsLoading(false));
              }}
              className="workbench-button workbench-button-secondary"
            >
              Refresh
            </button>
          </div>

          <div className="mt-6 grid gap-3">
            <label className="grid gap-2 text-sm font-medium">
              Search profiles
              <input
                value={profileQuery}
                onChange={(event) => setProfileQuery(event.target.value)}
                className="workbench-input"
                placeholder="Search profile ID, organism, strain, or synonym"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setSourceFilter(PROFILE_SOURCE_FILTERS.ALL)}
                className={`workbench-button ${sourceFilter === PROFILE_SOURCE_FILTERS.ALL ? "workbench-button-primary" : "workbench-button-secondary"}`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setSourceFilter(PROFILE_SOURCE_FILTERS.BUILTIN)}
                className={`workbench-button ${sourceFilter === PROFILE_SOURCE_FILTERS.BUILTIN ? "workbench-button-primary" : "workbench-button-secondary"}`}
              >
                Built-in
              </button>
              <button
                type="button"
                onClick={() => setSourceFilter(PROFILE_SOURCE_FILTERS.USER)}
                className={`workbench-button ${sourceFilter === PROFILE_SOURCE_FILTERS.USER ? "workbench-button-primary" : "workbench-button-secondary"}`}
              >
                User
              </button>
            </div>
          </div>

          <div className="mt-6 grid max-h-[760px] gap-4 overflow-y-auto pr-1">
            {isLoading ? (
              <div className="workbench-muted rounded-2xl border border-dashed workbench-border p-8 text-center">
                Loading profiles...
              </div>
            ) : visibleProfiles.length > 0 ? (
              profileGroups.map((group) => (
                <section key={group.speciesName} className="grid gap-3">
                  <h3 className="workbench-muted text-xs font-bold uppercase tracking-[0.14em]">
                    {group.speciesName}
                  </h3>
                  {group.profiles.map((profile) => {
                    const isExpanded = expandedProfileId === profile.profile_id;
                    return (
                      <article
                        key={profile.profile_id}
                        className={`rounded-2xl border workbench-border bg-white/50 p-4 ${isExpanded ? "shadow-sm" : ""}`}
                      >
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <button
                            type="button"
                            onClick={() => setExpandedProfileId(isExpanded ? "" : profile.profile_id)}
                            className="min-w-0 text-left"
                          >
                            <p className="workbench-foreground text-lg font-bold tracking-[-0.02em]">
                              {profile.canonical_name}
                            </p>
                            <p className="workbench-muted mt-1 text-sm">
                              {profile.profile_id} · {profile.strain || "No strain"}
                            </p>
                          </button>
                          <div className="flex flex-wrap gap-2">
                            <span className="inline-flex items-center rounded-full border workbench-border bg-white/70 px-3 py-1 leading-none text-xs font-bold uppercase tracking-wide text-[#3f4b43]">
                              {profile.read_only ? "Read-only" : "User"}
                            </span>
                            <button
                              type="button"
                              onClick={() => setExpandedProfileId(isExpanded ? "" : profile.profile_id)}
                              className="workbench-button workbench-button-secondary"
                            >
                              {isExpanded ? "Collapse" : "Expand"}
                            </button>
                            {!profile.read_only ? (
                              <>
                                <button
                                  type="button"
                                  onClick={() => startEditing(profile)}
                                  className="workbench-button workbench-button-secondary"
                                >
                                  Edit
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDelete(profile.profile_id)}
                                  className="workbench-button workbench-button-secondary workbench-red"
                                >
                                  Delete
                                </button>
                              </>
                            ) : null}
                          </div>
                        </div>

                        {isExpanded ? <ProfileDetailList profile={profile} /> : null}
                      </article>
                    );
                  })}
                </section>
              ))
            ) : profiles.length > 0 ? (
              <div className="workbench-muted rounded-2xl border border-dashed workbench-border p-8 text-center">
                No profiles match the current search or filter.
              </div>
            ) : (
              <div className="workbench-muted rounded-2xl border border-dashed workbench-border p-8 text-center">
                No profiles were returned by the backend.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
