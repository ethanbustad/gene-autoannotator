import assert from "node:assert/strict";
import test from "node:test";

import {
  filterJobsByBatch,
  getHiddenJobCount,
  getVisibleJobs,
  shouldShowRunningSpinner,
} from "./jobQueue.js";

const jobs = [
  { id: "running", status: "running" },
  { id: "queued-1", status: "queued" },
  { id: "queued-2", status: "queued" },
  { id: "completed", status: "completed" },
];

test("getVisibleJobs returns the first two jobs when collapsed", () => {
  assert.deepEqual(
    getVisibleJobs(jobs, false).map((job) => job.id),
    ["running", "queued-1"],
  );
});

test("getVisibleJobs returns all jobs when expanded", () => {
  assert.deepEqual(
    getVisibleJobs(jobs, true).map((job) => job.id),
    ["running", "queued-1", "queued-2", "completed"],
  );
});

test("getHiddenJobCount returns the number of jobs hidden by the compact view", () => {
  assert.equal(getHiddenJobCount(jobs), 2);
  assert.equal(getHiddenJobCount(jobs.slice(0, 2)), 0);
});

test("shouldShowRunningSpinner is true only for running jobs", () => {
  assert.equal(shouldShowRunningSpinner({ status: "running" }), true);
  assert.equal(shouldShowRunningSpinner({ status: "queued" }), false);
  assert.equal(shouldShowRunningSpinner({ status: "completed" }), false);
  assert.equal(shouldShowRunningSpinner({ status: "failed" }), false);
  assert.equal(shouldShowRunningSpinner(null), false);
});

test("filterJobsByBatch returns all jobs when batchId is missing", () => {
  assert.deepEqual(filterJobsByBatch(jobs, null), jobs);
  assert.deepEqual(filterJobsByBatch(jobs, ""), jobs);
});

test("filterJobsByBatch returns only jobs matching batch_id", () => {
  const batchJobs = [
    { id: "a", batch_id: "batch-1", status: "queued" },
    { id: "b", batch_id: "batch-2", status: "running" },
    { id: "c", batch_id: "batch-1", status: "completed" },
  ];
  assert.deepEqual(
    filterJobsByBatch(batchJobs, "batch-1").map((job) => job.id),
    ["a", "c"],
  );
});
