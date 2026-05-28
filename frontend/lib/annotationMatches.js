const COMPACT_MATCH_COUNT = 5;

export function getVisibleMatches(matches, expanded) {
  const normalizedMatches = Array.isArray(matches) ? matches : [];
  return expanded ? normalizedMatches : normalizedMatches.slice(0, COMPACT_MATCH_COUNT);
}

export function getHiddenMatchCount(matches) {
  const normalizedMatches = Array.isArray(matches) ? matches : [];
  return Math.max(0, normalizedMatches.length - COMPACT_MATCH_COUNT);
}
