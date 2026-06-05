import assert from "node:assert/strict";
import test from "node:test";

import {
  getGeneratedFieldRows,
  getMetadataRows,
  getPmcIdsAnalyzed,
} from "./annotationDisplay.js";

const annotation = {
  result: {
    annotation: {
      gene_id: "Rv0001",
      name: "dnaA",
      function: "Initiates chromosomal replication.",
      functional_category: ["information pathways", "DNA replication"],
      drug_susc_impact: "",
      infection_impact: null,
      essential_in_vitro: true,
      essential_in_vivo: false,
      annotation_notes: "Five papers were analyzed; support is mixed.",
      annotation_metadata: {
        literature: {
          total_papers_retrieved: 18,
          papers_analyzed: 5,
          sections_analyzed: 9,
          cumulative_relevance: 3.42,
          pmc_ids_analyzed: ["123", "456"],
        },
        llm_usage: {
          known_input_tokens: 1200,
          known_output_tokens: 345,
          known_total_tokens: 1545,
        },
        quality_flags: ["limited_literature"],
        duration_sec: 125,
      },
    },
  },
};

test("getGeneratedFieldRows returns the required fields in order with fallbacks", () => {
  assert.deepEqual(getGeneratedFieldRows(annotation).map((row) => row.key), [
    "functional_category",
    "function",
    "drug_susc_impact",
    "infection_impact",
    "essential_in_vitro",
    "essential_in_vivo",
  ]);
  assert.equal(getGeneratedFieldRows(annotation)[0].value, "information pathways, DNA replication");
  assert.equal(getGeneratedFieldRows(annotation)[2].value, "No supported data");
  assert.equal(getGeneratedFieldRows(annotation)[3].value, "No supported data");
  assert.equal(getGeneratedFieldRows(annotation)[4].value, "True");
  assert.equal(getGeneratedFieldRows(annotation)[5].value, "False");
});

test("getMetadataRows extracts requested metadata fields", () => {
  const rows = getMetadataRows(annotation);

  assert.deepEqual(rows.map((row) => row.key), [
    "annotation_notes",
    "total_papers",
    "papers_analyzed",
    "sections_analyzed",
    "cumulative_relevance",
    "quality_flags",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "duration",
  ]);
  assert.equal(rows[0].value, "Five papers were analyzed; support is mixed.");
  assert.equal(rows[1].value, "18");
  assert.equal(rows[5].value, "limited_literature");
  assert.equal(rows[6].value, "1200");
  assert.equal(rows[7].value, "345");
  assert.equal(rows[8].value, "1545");
  assert.equal(rows[9].value, "2m 5s");
});

test("getPmcIdsAnalyzed returns analyzed PMC IDs", () => {
  assert.deepEqual(getPmcIdsAnalyzed(annotation), ["123", "456"]);
});
