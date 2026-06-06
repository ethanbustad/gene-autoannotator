export const ANNOTATION_DATABASE_NAME = "gene_autoannotator";
export const ANNOTATION_COLLECTION_NAME = "annotations";

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function publicSummary(document) {
  return {
    id: document._id,
    profile_id: document.profile_id,
    canonical_name: document.canonical_name,
    species_name: document.species_name,
    strain: document.strain,
    normalized_locus: document.normalized_locus,
    gene_name: document.gene_name,
    generated_at: document.generated_at,
    version_count: document.version_count || 0,
  };
}

function publicDetail(document) {
  return {
    ...publicSummary(document),
    result: document.current.result,
    job_id: document.current.job_id,
    output_path: document.current.output_path,
  };
}

export async function searchStoredAnnotations(collection, query, limit = 20) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    return [];
  }

  const documents = await collection.find(
    {
      search_text: {
        $regex: escapeRegExp(normalizedQuery),
        $options: "i",
      },
    },
    { limit },
  ).toArray();

  return documents.map(publicSummary);
}

export async function getStoredAnnotation(collection, annotationId) {
  const document = await collection.findOne({ _id: annotationId });
  if (document === null) {
    return null;
  }
  return publicDetail(document);
}

export async function getStoredAnnotationVersions(collection, annotationId) {
  const document = await collection.findOne(
    { _id: annotationId },
    { projection: { versions: 1 } },
  );
  if (document === null) {
    return null;
  }
  return document.versions || [];
}

export async function getAnnotationStorageHealth({ databaseName, ping }) {
  await ping();
  return {
    status: "ok",
    database: databaseName,
    source: "next",
  };
}
