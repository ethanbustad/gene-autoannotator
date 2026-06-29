import assert from "node:assert/strict";
import test from "node:test";

import {
  buildProfilePayload,
  canEnableOrthologAllowed,
  sanitizeCustomFieldsForPayload,
  splitLines,
} from "./profileStore.js";

test("splitLines trims empty profile list entries", () => {
  assert.deepEqual(splitLines("abc\n\n def "), ["abc", "def"]);
});

test("buildProfilePayload serializes profile form fields", () => {
  assert.deepEqual(
    buildProfilePayload({
      profileId: "custom-profile",
      canonicalName: "Custom organism",
      speciesName: "Custom organism",
      strain: "Lab A",
      synonyms: "custom org",
      speciesSynonyms: "",
      strainSynonyms: "lab a",
      locusRegex: "^CUS_\\d+$",
      searchTerms: "Custom organism",
      targetPatterns: "Custom organism",
      offTargetPatterns: "Other organism",
      excludedSpeciesPatterns: "",
    }),
    {
      profile_id: "custom-profile",
      canonical_name: "Custom organism",
      species_name: "Custom organism",
      strain: "Lab A",
      synonyms: ["custom org"],
      species_synonyms: [],
      strain_synonyms: ["lab a"],
      locus_regex: "^CUS_\\d+$",
      search_terms: ["Custom organism"],
      target_patterns: ["Custom organism"],
      off_target_patterns: ["Other organism"],
      excluded_species_patterns: [],
      kegg_organism_code: null,
      custom_fields: [],
    },
  );
});

test("sanitizeCustomFieldsForPayload clears ortholog_allowed without kegg code", () => {
  assert.deepEqual(
    sanitizeCustomFieldsForPayload(
      [{ key: "function", ortholog_allowed: true }],
      "",
    ),
    [{ key: "function", ortholog_allowed: false }],
  );
  assert.equal(canEnableOrthologAllowed("mtu"), true);
  assert.equal(canEnableOrthologAllowed(""), false);
});
