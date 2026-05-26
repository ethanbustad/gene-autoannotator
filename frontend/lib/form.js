export function buildJobPayload(values) {
  const payload = {
    locus: values.locus?.trim(),
    allow_online_name_lookup: Boolean(values.allowOnlineNameLookup),
    refresh_gene_name_cache: Boolean(values.refreshGeneNameCache),
    cache_supplied_name: Boolean(values.cacheSuppliedName),
  };

  for (const [source, target] of [
    ["profile", "profile"],
    ["organism", "organism"],
    ["strain", "strain"],
    ["name", "name"],
  ]) {
    const value = values[source]?.trim();
    if (value) {
      payload[target] = value;
    }
  }

  return payload;
}

export function buildJobPrefillHref(annotation) {
  const params = new URLSearchParams();
  if (annotation.profile_id) {
    params.set("profile", annotation.profile_id);
  }
  if (annotation.normalized_locus) {
    params.set("locus", annotation.normalized_locus);
  }
  if (annotation.gene_name) {
    params.set("name", annotation.gene_name);
  }
  return `/jobs?${params.toString()}`;
}

export function formatElapsedSeconds(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) {
    return "Not started";
  }

  const total = Math.max(0, Math.floor(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainingSeconds = total % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${remainingSeconds}s`;
}

export function secondsSince(isoTimestamp) {
  if (!isoTimestamp) {
    return null;
  }
  return Math.max(0, Math.floor((Date.now() - Date.parse(isoTimestamp)) / 1000));
}
