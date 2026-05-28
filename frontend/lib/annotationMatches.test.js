import assert from "node:assert/strict";
import test from "node:test";

import { getHiddenMatchCount, getVisibleMatches } from "./annotationMatches.js";

const matches = Array.from({ length: 7 }, (_, index) => ({
  id: `match-${index + 1}`,
}));

test("getVisibleMatches returns the first five matches when collapsed", () => {
  assert.deepEqual(
    getVisibleMatches(matches, false).map((match) => match.id),
    ["match-1", "match-2", "match-3", "match-4", "match-5"],
  );
});

test("getVisibleMatches returns all matches when expanded", () => {
  assert.deepEqual(
    getVisibleMatches(matches, true).map((match) => match.id),
    ["match-1", "match-2", "match-3", "match-4", "match-5", "match-6", "match-7"],
  );
});

test("getHiddenMatchCount returns the number hidden by the compact view", () => {
  assert.equal(getHiddenMatchCount(matches), 2);
  assert.equal(getHiddenMatchCount(matches.slice(0, 5)), 0);
});
