import assert from "node:assert/strict";
import test from "node:test";

import { fetchBackendResponse } from "./backendProxy.js";

test("fetchBackendResponse returns service unavailable when FastAPI cannot be reached", async () => {
  const response = await fetchBackendResponse(
    new URL("http://127.0.0.1:8000/health"),
    { method: "GET", headers: new Headers() },
    async () => {
      throw new TypeError("fetch failed", {
        cause: Object.assign(new Error("connect ECONNREFUSED 127.0.0.1:8000"), {
          code: "ECONNREFUSED",
        }),
      });
    },
  );
  const payload = await response.json();

  assert.equal(response.status, 503);
  assert.equal(payload.detail, "Backend API is unavailable");
  assert.match(payload.message, /ECONNREFUSED|fetch failed/);
});
