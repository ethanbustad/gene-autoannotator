import assert from "node:assert/strict";
import test from "node:test";

import {
  buildJobPayload,
  buildJobPrefillHref,
  formatElapsedSeconds,
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
