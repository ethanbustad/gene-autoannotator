import assert from "node:assert/strict";
import test from "node:test";

import {
  buildJobPayload,
  buildJobPrefillHref,
  formatElapsedSeconds,
  formatJobElapsed,
} from "./form.js";

test("buildJobPayload omits empty optional fields and maps option names", () => {
  assert.deepEqual(
    buildJobPayload({
      profile: "mtb-h37rv",
      organism: "",
      strain: "",
      locus: "Rv0001",
      name: "",
      allowOnlineNameLookup: false,
      refreshGeneNameCache: true,
      cacheSuppliedName: false,
    }),
    {
      profile: "mtb-h37rv",
      locus: "Rv0001",
      allow_online_name_lookup: false,
      refresh_gene_name_cache: true,
      cache_supplied_name: false,
    },
  );
});

test("buildJobPayload supports name-only custom organism jobs", () => {
  assert.deepEqual(
    buildJobPayload({
      profile: "",
      organism: "Custom bacterium",
      strain: "Lab A",
      locus: "",
      name: "abc1",
      allowOnlineNameLookup: true,
      refreshGeneNameCache: false,
      cacheSuppliedName: false,
      locusRegex: "",
      searchTerms: "Custom bacterium\nC. bacterium",
      targetPatterns: "Custom bacterium",
      offTargetPatterns: "",
      excludedSpeciesPatterns: "",
    }),
    {
      organism: "Custom bacterium",
      strain: "Lab A",
      name: "abc1",
      allow_online_name_lookup: true,
      refresh_gene_name_cache: false,
      cache_supplied_name: false,
      search_terms: ["Custom bacterium", "C. bacterium"],
      target_patterns: ["Custom bacterium"],
    },
  );
});

test("buildJobPayload omits stale custom organism fields when a profile is selected", () => {
  assert.deepEqual(
    buildJobPayload({
      profile: "mtb-h37rv",
      organism: "Stale organism",
      strain: "Stale strain",
      locus: "Rv0001",
      name: "dnaA",
      allowOnlineNameLookup: true,
      refreshGeneNameCache: false,
      cacheSuppliedName: true,
      locusRegex: "^STALE_\\d+$",
      searchTerms: "stale search",
      targetPatterns: "stale target",
      offTargetPatterns: "stale off target",
      excludedSpeciesPatterns: "stale excluded",
    }),
    {
      profile: "mtb-h37rv",
      locus: "Rv0001",
      name: "dnaA",
      allow_online_name_lookup: true,
      refresh_gene_name_cache: false,
      cache_supplied_name: true,
    },
  );
});

test("buildJobPrefillHref creates a jobs URL from annotation identity", () => {
  assert.equal(
    buildJobPrefillHref({
      profile_id: "mtb-h37rv",
      normalized_locus: "Rv0001",
      gene_name: "dnaA",
    }),
    "/jobs?profile=mtb-h37rv&locus=Rv0001&name=dnaA",
  );
});

test("formatElapsedSeconds renders compact elapsed durations", () => {
  assert.equal(formatElapsedSeconds(5), "5s");
  assert.equal(formatElapsedSeconds(65), "1m 5s");
  assert.equal(formatElapsedSeconds(3661), "1h 1m");
});

test("formatJobElapsed shows a placeholder before a job starts", () => {
  assert.equal(
    formatJobElapsed({
      status: "queued",
      created_at: "2026-05-27T10:00:00.000Z",
      started_at: null,
      finished_at: null,
    }, Date.parse("2026-05-27T10:05:00.000Z")),
    "--",
  );
});

test("formatJobElapsed counts running jobs from started_at", () => {
  assert.equal(
    formatJobElapsed({
      status: "running",
      created_at: "2026-05-27T09:55:00.000Z",
      started_at: "2026-05-27T10:00:00.000Z",
      finished_at: null,
    }, Date.parse("2026-05-27T10:02:05.000Z")),
    "2m 5s",
  );
});

test("formatJobElapsed stops counting when a job finishes", () => {
  assert.equal(
    formatJobElapsed({
      status: "completed",
      created_at: "2026-05-27T09:55:00.000Z",
      started_at: "2026-05-27T10:00:00.000Z",
      finished_at: "2026-05-27T10:03:01.000Z",
    }, Date.parse("2026-05-27T11:00:00.000Z")),
    "3m 1s",
  );
});
