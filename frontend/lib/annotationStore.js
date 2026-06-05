import { MongoClient } from "mongodb";

const DEFAULT_DATABASE_NAME = "gene_autoannotator";
const DEFAULT_COLLECTION_NAME = "annotations";
const DEFAULT_SERVER_SELECTION_TIMEOUT_MS = 1000;

const cachedClientPromisesByFactory = new Map();

function escapeRegex(value) {
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

export class DisabledAnnotationStore {
  health() {
    return { status: "unconfigured", message: "MONGO_URI is not set" };
  }

  raiseUnavailable() {
    throw new Error("MONGO_URI is not configured");
  }

  search() {
    this.raiseUnavailable();
  }

  get() {
    this.raiseUnavailable();
  }

  getVersions() {
    this.raiseUnavailable();
  }
}

export class MongoAnnotationStore {
  constructor(
    mongoUri,
    {
      databaseName = DEFAULT_DATABASE_NAME,
      collectionName = DEFAULT_COLLECTION_NAME,
      collection = null,
      clientFactory = MongoClient,
    } = {},
  ) {
    this.mongoUri = mongoUri;
    this.databaseName = databaseName;
    this.collectionName = collectionName;
    this.collection = collection;
    this.clientFactory = clientFactory;
  }

  async getCollection() {
    if (this.collection) {
      return this.collection;
    }

    let cachedClientPromises = cachedClientPromisesByFactory.get(this.clientFactory);
    if (!cachedClientPromises) {
      cachedClientPromises = new Map();
      cachedClientPromisesByFactory.set(this.clientFactory, cachedClientPromises);
    }

    if (!cachedClientPromises.has(this.mongoUri)) {
      const client = new this.clientFactory(this.mongoUri, {
        serverSelectionTimeoutMS: DEFAULT_SERVER_SELECTION_TIMEOUT_MS,
      });
      const clientPromise = client
        .connect()
        .then(() => client)
        .catch((error) => {
          cachedClientPromises.delete(this.mongoUri);
          throw error;
        });
      cachedClientPromises.set(this.mongoUri, clientPromise);
    }

    const client = await cachedClientPromises.get(this.mongoUri);
    this.collection = client.db(this.databaseName).collection(this.collectionName);
    return this.collection;
  }

  async health() {
    try {
      const collection = await this.getCollection();
      await collection.db.admin().command({ ping: 1 });
      return { status: "ok", database: this.databaseName };
    } catch (error) {
      return { status: "unavailable", message: error.message };
    }
  }

  async search(query, limit = 20) {
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      return [];
    }

    const collection = await this.getCollection();
    const documents = await collection
      .find(
        {
          search_text: { $regex: escapeRegex(normalizedQuery), $options: "i" },
        },
        { limit },
      )
      .toArray();
    return documents.map(publicSummary);
  }

  async get(annotationId) {
    const collection = await this.getCollection();
    const document = await collection.findOne({ _id: annotationId });
    return document ? publicDetail(document) : null;
  }

  async getVersions(annotationId) {
    const collection = await this.getCollection();
    const document = await collection.findOne(
      { _id: annotationId },
      { projection: { versions: 1 } },
    );
    return document ? document.versions || [] : null;
  }
}

export function annotationStoreFromEnv(env = process.env) {
  const mongoUri = env.MONGO_URI || env.MONGODB_URI;
  if (!mongoUri) {
    return new DisabledAnnotationStore();
  }
  return new MongoAnnotationStore(mongoUri);
}
