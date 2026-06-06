const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const BROWSER_API_BASE_URL = "/api/backend";
const ANNOTATION_API_BASE_URL = "/api/annotations";

function getBrowserApiBaseUrl() {
  if (typeof window === "undefined") {
    return null;
  }
  return BROWSER_API_BASE_URL;
}

export function getApiBaseUrl() {
  // Server components can call FastAPI directly, but browser components always
  // use the Next proxy so CORS and deployment topology stay centralized.
  const browserApiBaseUrl = getBrowserApiBaseUrl();

  if (browserApiBaseUrl) {
    return browserApiBaseUrl;
  }

  return process.env.BACKEND_API_BASE_URL || DEFAULT_API_BASE_URL;
}

export function getAnnotationApiBaseUrl() {
  return ANNOTATION_API_BASE_URL;
}

async function apiFetchFrom(baseUrl, path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    cache: "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail || `Backend returned HTTP ${response.status}`;
    throw new Error(detail);
  }
  return payload;
}

async function apiFetch(path, options = {}) {
  return apiFetchFrom(getApiBaseUrl(), path, options);
}

async function annotationApiFetch(path, options = {}) {
  return apiFetchFrom(getAnnotationApiBaseUrl(), path, options);
}

export async function getHealth() {
  return apiFetch("/health");
}

export async function getProfiles() {
  return apiFetch("/profiles");
}

export async function validateJob(payload) {
  return apiFetch("/validate", {
    method: "POST",
    body: JSON.stringify({
      profile: payload.profile,
      organism: payload.organism,
      strain: payload.strain,
      locus: payload.locus,
    }),
  });
}

export async function createJob(payload) {
  return apiFetch("/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listJobs(order = "queue") {
  return apiFetch(`/jobs?order=${encodeURIComponent(order)}`);
}

export async function clearFinishedJobHistory() {
  return apiFetch("/jobs/history", {
    method: "DELETE",
  });
}

export async function searchAnnotations(query) {
  return annotationApiFetch(`/search?query=${encodeURIComponent(query)}`);
}

export async function getAnnotation(annotationId) {
  return annotationApiFetch(`/${encodeURIComponent(annotationId)}`);
}

export async function getAnnotationVersions(annotationId) {
  return annotationApiFetch(`/${encodeURIComponent(annotationId)}/versions`);
}

export async function getAnnotationHealth() {
  const response = await fetch(`${getAnnotationApiBaseUrl()}/health`, {
    cache: "no-store",
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok && !payload) {
    throw new Error(`Annotation health returned HTTP ${response.status}`);
  }
  return payload;
}
