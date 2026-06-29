export const CURRENT_VERSION_KEY = "current";

export function getTotalVersionCount(annotation, versions) {
  if (!annotation) {
    return 0;
  }
  const olderCount = versions?.length ?? annotation.version_count ?? 0;
  return olderCount + 1;
}

export function buildVersionOptions(annotation, versions) {
  if (!annotation) {
    return [];
  }

  const olderVersions = versions || [];
  const total = olderVersions.length + 1;
  const options = [
    {
      key: CURRENT_VERSION_KEY,
      versionNumber: total,
      isCurrent: true,
      gene_name: annotation.gene_name,
      generated_at: annotation.generated_at,
      job_id: annotation.job_id,
    },
  ];

  // versions[0] is the most recently superseded run; assign descending version numbers.
  olderVersions.forEach((version, index) => {
    options.push({
      key: version.version_id,
      versionNumber: total - 1 - index,
      isCurrent: false,
      gene_name: version.gene_name,
      generated_at: version.generated_at,
      job_id: version.job_id,
      version,
    });
  });

  return options;
}

export function annotationViewForVersion(annotation, selectedKey, versions) {
  if (!annotation || selectedKey === CURRENT_VERSION_KEY) {
    return annotation;
  }

  const version = (versions || []).find((item) => item.version_id === selectedKey);
  if (!version) {
    return annotation;
  }

  return {
    ...annotation,
    gene_name: version.gene_name ?? annotation.gene_name,
    generated_at: version.generated_at,
    job_id: version.job_id,
    output_path: version.output_path,
    result: version.result,
  };
}

export function formatVersionLabel(option) {
  const suffix = option.isCurrent ? " (current)" : "";
  return `Version ${option.versionNumber}${suffix}`;
}
