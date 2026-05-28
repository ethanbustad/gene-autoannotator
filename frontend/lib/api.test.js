import assert from "node:assert/strict";
import test from "node:test";

import { getApiBaseUrl } from "./api.js";

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

test("getApiBaseUrl uses the same-origin backend proxy in the browser", () => {
  withApiBaseUrl(undefined, () => {
    withBrowserLocation({ protocol: "http:", hostname: "10.1.2.3" }, () => {
      assert.equal(getApiBaseUrl(), "/api/backend");
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

