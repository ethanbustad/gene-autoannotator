import assert from "node:assert/strict";
import test from "node:test";

import {
  DisabledAnnotationStore,
  MongoAnnotationStore,
  annotationStoreFromEnv,
} from "./annotationStore.js";

function makeDocument(overrides = {}) {
  return {
    _id: "mtb-h37rv:Rv0001",
    profile_id: "mtb-h37rv",
    canonical_name: "Mycobacterium tuberculosis H37Rv",
    species_name: "Mycobacterium tuberculosis",
    strain: "H37Rv",
    normalized_locus: "Rv0001",
    gene_name: "dnaA",
    generated_at: "2026-01-01T00:00:00Z",
    version_count: 1,
    search_text: "mtb-h37rv rv0001 dnaa",
    current: {
      job_id: "job-1",
      output_path: "gen_json/gen_Rv0001.json",
      result: { annotation: { gene_id: "Rv0001", name: "dnaA" } },
    },
    versions: [
      {
        version_id: "old-version",
        job_id: "job-0",
        generated_at: "2025-12-01T00:00:00Z",
        gene_name: "dnaA old",
        result: { annotation: { gene_id: "Rv0001", name: "dnaA old" } },
      },
    ],
    ...overrides,
  };
}

class FakeCursor {
  constructor(documents) {
    this.documents = documents;
  }

  async toArray() {
    return this.documents;
  }
}

class FakeCollection {
  constructor(documents = []) {
    this.documents = documents;
    this.db = {
      admin: () => ({
        command: async (command) => {
          assert.deepEqual(command, { ping: 1 });
          return { ok: 1 };
        },
      }),
    };
    this.lastFind = null;
    this.lastFindOne = null;
  }

  find(query, options) {
    this.lastFind = { query, options };
    return new FakeCursor(this.documents.slice(0, options.limit));
  }

  async findOne(query, projection) {
    this.lastFindOne = { query, projection };
    return this.documents.find((document) => document._id === query._id) || null;
  }
}

test("annotationStoreFromEnv returns a disabled store without Mongo configuration", () => {
  const store = annotationStoreFromEnv({});

  assert.ok(store instanceof DisabledAnnotationStore);
  assert.deepEqual(store.health(), {
    status: "unconfigured",
    message: "MONGO_URI is not set",
  });
});

test("DisabledAnnotationStore rejects data access without Mongo configuration", () => {
  const store = new DisabledAnnotationStore();

  assert.throws(() => store.search("dnaA"), /MONGO_URI is not configured/);
  assert.throws(() => store.get("mtb-h37rv:Rv0001"), /MONGO_URI is not configured/);
  assert.throws(() => store.getVersions("mtb-h37rv:Rv0001"), /MONGO_URI is not configured/);
});

test("MongoAnnotationStore health pings the configured collection", async () => {
  const store = new MongoAnnotationStore("mongodb://example", {
    collection: new FakeCollection(),
  });

  assert.deepEqual(await store.health(), {
    status: "ok",
    database: "gene_autoannotator",
  });
});

test("MongoAnnotationStore retries connection after a failed connect attempt", async () => {
  let connectAttempts = 0;

  class FlakyClient {
    constructor(mongoUri, options) {
      assert.equal(mongoUri, "mongodb://flaky");
      assert.deepEqual(options, { serverSelectionTimeoutMS: 1000 });
    }

    async connect() {
      connectAttempts += 1;
      if (connectAttempts === 1) {
        throw new Error("first connect failed");
      }
      return this;
    }

    db(databaseName) {
      assert.equal(databaseName, "gene_autoannotator");
      return {
        collection: (collectionName) => {
          assert.equal(collectionName, "annotations");
          return new FakeCollection();
        },
      };
    }
  }

  const firstStore = new MongoAnnotationStore("mongodb://flaky", {
    clientFactory: FlakyClient,
  });
  const secondStore = new MongoAnnotationStore("mongodb://flaky", {
    clientFactory: FlakyClient,
  });

  assert.deepEqual(await firstStore.health(), {
    status: "unavailable",
    message: "first connect failed",
  });
  assert.deepEqual(await secondStore.health(), {
    status: "ok",
    database: "gene_autoannotator",
  });
  assert.equal(connectAttempts, 2);
});

test("MongoAnnotationStore search returns public summaries", async () => {
  const collection = new FakeCollection([makeDocument()]);
  const store = new MongoAnnotationStore("mongodb://example", { collection });

  const matches = await store.search("dnaA", 20);

  assert.deepEqual(collection.lastFind.query, {
    search_text: { $regex: "dnaA", $options: "i" },
  });
  assert.equal(collection.lastFind.options.limit, 20);
  assert.deepEqual(matches, [
    {
      id: "mtb-h37rv:Rv0001",
      profile_id: "mtb-h37rv",
      canonical_name: "Mycobacterium tuberculosis H37Rv",
      species_name: "Mycobacterium tuberculosis",
      strain: "H37Rv",
      normalized_locus: "Rv0001",
      gene_name: "dnaA",
      generated_at: "2026-01-01T00:00:00Z",
      version_count: 1,
    },
  ]);
});

test("MongoAnnotationStore search escapes regex metacharacters", async () => {
  const collection = new FakeCollection([makeDocument()]);
  const store = new MongoAnnotationStore("mongodb://example", { collection });

  await store.search("dnaA.*", 5);

  assert.deepEqual(collection.lastFind.query, {
    search_text: { $regex: "dnaA\\.\\*", $options: "i" },
  });
  assert.equal(collection.lastFind.options.limit, 5);
});

test("MongoAnnotationStore get returns current annotation detail", async () => {
  const store = new MongoAnnotationStore("mongodb://example", {
    collection: new FakeCollection([makeDocument()]),
  });

  const annotation = await store.get("mtb-h37rv:Rv0001");

  assert.equal(annotation.id, "mtb-h37rv:Rv0001");
  assert.equal(annotation.job_id, "job-1");
  assert.equal(annotation.output_path, "gen_json/gen_Rv0001.json");
  assert.deepEqual(annotation.result, {
    annotation: { gene_id: "Rv0001", name: "dnaA" },
  });
});

test("MongoAnnotationStore getVersions returns older versions", async () => {
  const collection = new FakeCollection([makeDocument()]);
  const store = new MongoAnnotationStore("mongodb://example", { collection });

  const versions = await store.getVersions("mtb-h37rv:Rv0001");

  assert.deepEqual(collection.lastFindOne.projection, { projection: { versions: 1 } });
  assert.equal(versions[0].version_id, "old-version");
});

test("MongoAnnotationStore getVersions returns an empty array when no versions exist", async () => {
  const store = new MongoAnnotationStore("mongodb://example", {
    collection: new FakeCollection([makeDocument({ versions: undefined })]),
  });

  assert.deepEqual(await store.getVersions("mtb-h37rv:Rv0001"), []);
});

test("MongoAnnotationStore returns null for missing annotation detail and versions", async () => {
  const store = new MongoAnnotationStore("mongodb://example", {
    collection: new FakeCollection([]),
  });

  assert.equal(await store.get("missing"), null);
  assert.equal(await store.getVersions("missing"), null);
});
