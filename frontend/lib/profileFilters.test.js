import assert from "node:assert/strict";
import test from "node:test";

import {
  filterProfiles,
  groupProfilesBySpecies,
  PROFILE_SOURCE_FILTERS,
} from "./profileFilters.js";

const profiles = [
  {
    profile_id: "mtb-h37rv",
    canonical_name: "Mycobacterium tuberculosis H37Rv",
    species_name: "Mycobacterium tuberculosis",
    strain: "H37Rv",
    source: "builtin",
    read_only: true,
    synonyms: ["Mtb"],
  },
  {
    profile_id: "ecoli-k12-mg1655",
    canonical_name: "Escherichia coli K-12 MG1655",
    species_name: "Escherichia coli",
    strain: "K-12 MG1655",
    source: "user",
    read_only: false,
    species_synonyms: ["E. coli"],
  },
  {
    profile_id: "ecoli-bl21",
    canonical_name: "Escherichia coli BL21",
    species_name: "Escherichia coli",
    strain: "BL21",
    source: "user",
    read_only: false,
  },
];

test("filterProfiles searches profile names identifiers strains and synonyms", () => {
  assert.deepEqual(
    filterProfiles(profiles, { query: "e. coli", sourceFilter: "all" }).map(
      (profile) => profile.profile_id,
    ),
    ["ecoli-k12-mg1655"],
  );

  assert.deepEqual(
    filterProfiles(profiles, { query: "h37", sourceFilter: "all" }).map(
      (profile) => profile.profile_id,
    ),
    ["mtb-h37rv"],
  );
});

test("filterProfiles filters built-in and user profile sources", () => {
  assert.deepEqual(
    filterProfiles(profiles, { query: "", sourceFilter: PROFILE_SOURCE_FILTERS.BUILTIN }).map(
      (profile) => profile.profile_id,
    ),
    ["mtb-h37rv"],
  );
  assert.deepEqual(
    filterProfiles(profiles, { query: "", sourceFilter: PROFILE_SOURCE_FILTERS.USER }).map(
      (profile) => profile.profile_id,
    ),
    ["ecoli-k12-mg1655", "ecoli-bl21"],
  );
});

test("groupProfilesBySpecies groups filtered rows by species name", () => {
  assert.deepEqual(groupProfilesBySpecies(profiles), [
    {
      speciesName: "Mycobacterium tuberculosis",
      profiles: [profiles[0]],
    },
    {
      speciesName: "Escherichia coli",
      profiles: [profiles[1], profiles[2]],
    },
  ]);
});
