import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const projectRoot = process.cwd();

async function readProjectFile(relativePath) {
  return readFile(path.join(projectRoot, relativePath), "utf8");
}

test("JobWorkspace integrates batch queue filtering and summary card", async () => {
  const workspace = await readProjectFile("components/JobWorkspace.js");

  assert.match(workspace, /filterJobsByBatch/);
  assert.match(workspace, /getBatch/);
  assert.match(workspace, /BatchSummaryCard/);
  assert.match(workspace, /setBatchFilterActive\(true\)/);
  assert.match(workspace, /Show batch only/);
  assert.match(workspace, /Show all jobs/);
});

test("completed job annotation link falls back to name and preflight identifiers", async () => {
  const workspace = await readProjectFile("components/JobWorkspace.js");

  assert.match(
    workspace,
    /const annotationQuery =\s*request\.locus \|\|\s*request\.name \|\|\s*request\.target_preflight\?\.resolved_name \|\|\s*request\.target_preflight\?\.primary_identifier \|\|\s*"";/s,
  );
  assert.match(
    workspace,
    /href=\{`\/annotations\?query=\$\{encodeURIComponent\(annotationQuery\)\}`\}/,
  );
});
