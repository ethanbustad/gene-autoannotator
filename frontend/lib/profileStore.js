export function splitLines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function buildProfilePayload(values) {
  const payload = {
    profile_id: values.profileId?.trim(),
    canonical_name: values.canonicalName?.trim(),
    species_name: values.speciesName?.trim(),
    strain: values.strain?.trim() || null,
    synonyms: splitLines(values.synonyms),
    species_synonyms: splitLines(values.speciesSynonyms),
    strain_synonyms: splitLines(values.strainSynonyms),
    locus_regex: values.locusRegex?.trim() || null,
    search_terms: splitLines(values.searchTerms),
    target_patterns: splitLines(values.targetPatterns),
    off_target_patterns: splitLines(values.offTargetPatterns),
    excluded_species_patterns: splitLines(values.excludedSpeciesPatterns),
  };
  return payload;
}
