export const PROFILE_SOURCE_FILTERS = {
  ALL: "all",
  BUILTIN: "builtin",
  USER: "user",
};

function fieldValues(profile) {
  return [
    profile.profile_id,
    profile.canonical_name,
    profile.species_name,
    profile.strain,
    ...(profile.synonyms || []),
    ...(profile.species_synonyms || []),
    ...(profile.strain_synonyms || []),
  ];
}

function normalize(value) {
  return String(value || "").trim().toLocaleLowerCase();
}

function profileMatchesQuery(profile, query) {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery) {
    return true;
  }
  return fieldValues(profile).some((value) =>
    normalize(value).includes(normalizedQuery),
  );
}

function profileMatchesSource(profile, sourceFilter) {
  if (sourceFilter === PROFILE_SOURCE_FILTERS.BUILTIN) {
    return profile.source === "builtin" || profile.read_only === true;
  }
  if (sourceFilter === PROFILE_SOURCE_FILTERS.USER) {
    return profile.source !== "builtin" && profile.read_only !== true;
  }
  return true;
}

export function filterProfiles(profiles, { query = "", sourceFilter = PROFILE_SOURCE_FILTERS.ALL } = {}) {
  return profiles.filter(
    (profile) =>
      profileMatchesSource(profile, sourceFilter) &&
      profileMatchesQuery(profile, query),
  );
}

export function groupProfilesBySpecies(profiles) {
  const groups = [];
  const bySpecies = new Map();
  for (const profile of profiles) {
    const speciesName = profile.species_name || "Unknown species";
    if (!bySpecies.has(speciesName)) {
      const group = { speciesName, profiles: [] };
      bySpecies.set(speciesName, group);
      groups.push(group);
    }
    bySpecies.get(speciesName).profiles.push(profile);
  }
  return groups;
}
