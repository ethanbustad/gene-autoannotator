const DEFAULT_BACKEND_API_BASE_URL = "http://127.0.0.1:8000";
const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
]);

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function getBackendApiBaseUrl() {
  return process.env.BACKEND_API_BASE_URL || DEFAULT_BACKEND_API_BASE_URL;
}

function copyProxyHeaders(headers) {
  const copied = new Headers(headers);
  for (const header of HOP_BY_HOP_HEADERS) {
    copied.delete(header);
  }
  return copied;
}

async function buildBackendUrl(request, context) {
  const params = await context.params;
  const path = params.path || [];
  const backendUrl = new URL(path.map(encodeURIComponent).join("/"), `${getBackendApiBaseUrl()}/`);
  backendUrl.search = new URL(request.url).search;
  return backendUrl;
}

async function proxyRequest(request, context) {
  const backendUrl = await buildBackendUrl(request, context);
  const headers = copyProxyHeaders(request.headers);
  headers.delete("host");

  const init = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  const response = await fetch(backendUrl, init);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: copyProxyHeaders(response.headers),
  });
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;

