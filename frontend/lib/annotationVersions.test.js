import assert from "node:assert/strict";
import test from "node:test";

import {
  annotationViewForVersion,
  buildVersionOptions,
  formatVersionLabel,
  getTotalVersionCount,
} from "./annotationVersions.js";

const baseAnnotation = {
  id: "mtb-h37rv:Rv0001",
  gene_name: "dnaA current",
  generated_at: "2026-03-01T00:00:00Z",
  job_id: "job-3",
  version_count: 2,
  result: { annotation: { function: "current function" } },
};

const versions = [
  {
    version_id: "version-2",
    gene_name: "dnaA v2",
    generated_at: "2026-02-01T00:00:00Z",
    job_id: "job-2",
    result: { annotation: { function: "second function" } },
  },
  {
    version_id: "version-1",
    gene_name: "dnaA v1",
    generated_at: "2026-01-01T00:00:00Z",
    job_id: "job-1",
    result: { annotation: { function: "first function" } },
  },
];

test("getTotalVersionCount includes the current annotation", () => {
  assert.equal(getTotalVersionCount(baseAnnotation, versions), 3);
  assert.equal(getTotalVersionCount({ version_count: 0 }, []), 1);
});

test("buildVersionOptions lists current first with descending version numbers", () => {
  const options = buildVersionOptions(baseAnnotation, versions);

  assert.equal(options.length, 3);
  assert.equal(options[0].key, "current");
  assert.equal(options[0].versionNumber, 3);
  assert.equal(options[0].isCurrent, true);
  assert.equal(options[1].key, "version-2");
  assert.equal(options[1].versionNumber, 2);
  assert.equal(options[2].key, "version-1");
  assert.equal(options[2].versionNumber, 1);
});

test("annotationViewForVersion swaps in the selected historical payload", () => {
  const view = annotationViewForVersion(baseAnnotation, "version-1", versions);

  assert.equal(view.gene_name, "dnaA v1");
  assert.equal(view.job_id, "job-1");
  assert.equal(view.result.annotation.function, "first function");
  assert.equal(view.id, "mtb-h37rv:Rv0001");
});

test("formatVersionLabel marks the current version", () => {
  assert.equal(
    formatVersionLabel({ versionNumber: 3, isCurrent: true }),
    "Version 3 (current)",
  );
  assert.equal(formatVersionLabel({ versionNumber: 1, isCurrent: false }), "Version 1");
});
