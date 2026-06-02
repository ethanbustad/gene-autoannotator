const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const BROWSER_API_BASE_URL = "/api/backend";

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

async function apiFetch(path, options = {}) {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
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
  return apiFetch(`/annotations/search?query=${encodeURIComponent(query)}`);
}

export async function getAnnotation(annotationId) {
  return apiFetch(`/annotations/${encodeURIComponent(annotationId)}`);
}

export async function getAnnotationVersions(annotationId) {
  return apiFetch(`/annotations/${encodeURIComponent(annotationId)}/versions`);
}
