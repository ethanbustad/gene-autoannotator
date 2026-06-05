import assert from "node:assert/strict";
import test from "node:test";

import {
  getAnnotation,
  getAnnotationHealth,
  getAnnotationVersions,
  getApiBaseUrl,
  searchAnnotations,
} from "./api.js";

function withBrowserLocation(location, callback) {
  const originalWindow = globalThis.window;
  globalThis.window = { location };
  try {
    callback();
  } finally {
    if (originalWindow === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = originalWindow;
    }
  }
}

function withApiBaseUrl(value, callback) {
  const originalValue = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (value === undefined) {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  } else {
    process.env.NEXT_PUBLIC_API_BASE_URL = value;
  }

  try {
    callback();
  } finally {
    if (originalValue === undefined) {
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
    } else {
      process.env.NEXT_PUBLIC_API_BASE_URL = originalValue;
    }
  }
}

function withBackendApiBaseUrl(value, callback) {
  const originalValue = process.env.BACKEND_API_BASE_URL;
  if (value === undefined) {
    delete process.env.BACKEND_API_BASE_URL;
  } else {
    process.env.BACKEND_API_BASE_URL = value;
  }

  try {
    callback();
  } finally {
    if (originalValue === undefined) {
      delete process.env.BACKEND_API_BASE_URL;
    } else {
      process.env.BACKEND_API_BASE_URL = originalValue;
    }
  }
}

function withoutBrowser(callback) {
  const originalWindow = globalThis.window;
  delete globalThis.window;
  try {
    callback();
  } finally {
    if (originalWindow !== undefined) {
      globalThis.window = originalWindow;
    }
  }
}

test("getApiBaseUrl uses the same-origin backend proxy in the browser", () => {
  withApiBaseUrl(undefined, () => {
    withBrowserLocation({ protocol: "http:", hostname: "10.1.2.3" }, () => {
      assert.equal(getApiBaseUrl(), "/api/backend");
    });
  });
});

test("getApiBaseUrl ignores public API URLs on the server", () => {
  withApiBaseUrl("http://10.158.45.197:8000", () => {
    withBackendApiBaseUrl(undefined, () => {
      withoutBrowser(() => {
        assert.equal(getApiBaseUrl(), "http://127.0.0.1:8000");
      });
    });
  });
});

test("getApiBaseUrl uses the private backend API URL on the server", () => {
  withApiBaseUrl("http://10.158.45.197:8000", () => {
    withBackendApiBaseUrl("http://backend.internal:8000", () => {
      withoutBrowser(() => {
        assert.equal(getApiBaseUrl(), "http://backend.internal:8000");
      });
    });
  });
});

test("getApiBaseUrl ignores a loopback API URL in the browser", () => {
  withApiBaseUrl("http://localhost:8000", () => {
    withBrowserLocation({ protocol: "http:", hostname: "10.1.2.3" }, () => {
      assert.equal(getApiBaseUrl(), "/api/backend");
    });
  });
});

test("getApiBaseUrl ignores a stale network API URL in the browser", () => {
  withApiBaseUrl("http://10.158.45.197:8000", () => {
    withBrowserLocation({ protocol: "http:", hostname: "10.19.178.136" }, () => {
      assert.equal(getApiBaseUrl(), "/api/backend");
    });
  });
});

async function withMockFetch(callback) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ query: "dnaA", matches: [], versions: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await callback(calls);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test("annotation helpers use the Next-side annotation API", async () => {
  await withMockFetch(async (calls) => {
    await searchAnnotations("dnaA");
    await getAnnotation("mtb-h37rv:Rv0001");
    await getAnnotationVersions("mtb-h37rv:Rv0001");
    await getAnnotationHealth();

    assert.equal(calls[0].url, "/api/annotations/search?query=dnaA");
    assert.equal(calls[1].url, "/api/annotations/mtb-h37rv%3ARv0001");
    assert.equal(calls[2].url, "/api/annotations/mtb-h37rv%3ARv0001/versions");
    assert.equal(calls[3].url, "/api/annotations/health");
  });
});

