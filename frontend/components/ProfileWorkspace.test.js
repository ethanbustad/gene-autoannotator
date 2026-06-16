import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const projectRoot = process.cwd();

async function readProjectFile(relativePath) {
  return readFile(path.join(projectRoot, relativePath), "utf8");
}

test("profiles page is reachable from the workbench navigation", async () => {
  const appShell = await readProjectFile("components/AppShell.js");

  assert.match(
    appShell,
    /const navItems = \[\s*\{ href: "\/", label: "Guide" \},\s*\{ href: "\/jobs", label: "Jobs" \},\s*\{ href: "\/profiles", label: "Profiles" \},\s*\{ href: "\/annotations", label: "Annotations" \},\s*\];/s,
  );
});

test("profiles route renders the profile workspace in the app shell", async () => {
  const route = await readProjectFile("app/profiles/page.js");

  assert.match(route, /import AppShell from "\.\.\/\.\.\/components\/AppShell";/);
  assert.match(route, /import ProfileWorkspace from "\.\.\/\.\.\/components\/ProfileWorkspace";/);
  assert.match(route, /title: "Profiles · Gene Autoannotator"/);
  assert.match(route, /<AppShell>\s*<ProfileWorkspace \/>\s*<\/AppShell>/s);
});

test("profile workspace supports editing all reusable profile fields", async () => {
  const workspace = await readProjectFile("components/ProfileWorkspace.js");

  assert.match(workspace, /"use client";/);
  assert.match(
    workspace,
    /import \{\s*createProfile,\s*deleteProfile,\s*getProfiles,\s*updateProfile,\s*\} from "\.\.\/lib\/api";/s,
  );
  assert.match(workspace, /import \{ buildProfilePayload \} from "\.\.\/lib\/profileStore";/);

  for (const field of [
    "profileId",
    "canonicalName",
    "speciesName",
    "strain",
    "synonyms",
    "speciesSynonyms",
    "strainSynonyms",
    "locusRegex",
    "searchTerms",
    "targetPatterns",
    "offTargetPatterns",
    "excludedSpeciesPatterns",
  ]) {
    assert.match(workspace, new RegExp(`\\b${field}\\b`));
  }

  assert.match(workspace, /getProfiles\(\)/);
  assert.match(workspace, /buildProfilePayload\(form\)/);
  assert.match(workspace, /updateProfile\(editingProfileId,/);
  assert.match(workspace, /createProfile\(payload\)/);
  assert.match(workspace, /deleteProfile\(profileId\)/);
  assert.match(workspace, /profile\.read_only/);
});

test("resetting the profile form clears stale edit status text", async () => {
  const workspace = await readProjectFile("components/ProfileWorkspace.js");

  assert.match(
    workspace,
    /function resetForm\(\) \{\s*setForm\(emptyForm\);\s*setEditingProfileId\(""\);\s*setStatusMessage\(""\);\s*\}/s,
  );
  assert.match(workspace, /onClick=\{resetForm\}/);
});

test("profile detail cards include synonym fields", async () => {
  const workspace = await readProjectFile("components/ProfileWorkspace.js");

  assert.match(workspace, /\["Profile synonyms", profile\.synonyms\?\.join\(", "\)\]/);
  assert.match(workspace, /\["Species synonyms", profile\.species_synonyms\?\.join\(", "\)\]/);
  assert.match(workspace, /\["Strain synonyms", profile\.strain_synonyms\?\.join\(", "\)\]/);
});

test("profile source chip centers its label", async () => {
  const workspace = await readProjectFile("components/ProfileWorkspace.js");

  assert.match(
    workspace,
    /className="inline-flex items-center rounded-full border workbench-border bg-white\/70 px-3 py-1 leading-none text-xs font-bold uppercase tracking-wide text-\[#3f4b43\]"/,
  );
});
