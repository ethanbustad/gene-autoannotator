# Gene Autoannotator Frontend

This [Next.js](https://nextjs.org) app is the web interface for the gene
autoannotator API. It has pages for usage guidance, queued job submission, and
searching generated annotation history.

## Getting Started

Copy the example environment file and configure both the Python API and MongoDB
for the Next.js server process:

```bash
cp .env.example .env.local
```

`BACKEND_API_BASE_URL` points Next.js server/proxy calls at FastAPI for
profiles, validation, jobs, queue state, and backend health. `MONGO_URI` or
`MONGODB_URI` lets the Next.js server read annotation history/search directly
from MongoDB, so `/annotations` can keep working while FastAPI is offline.

Then run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

The Python backend should be running separately on port `8000` for job-related
actions. Browser job API calls still go through the same-origin `/api/backend`
proxy, so remote devices only need to reach the frontend on port `3000`. If
FastAPI is not on the same machine as Next.js, set `BACKEND_API_BASE_URL` to its
internal URL.

Annotation search/review uses `/api/annotations/*` server routes. Those routes
read MongoDB from the Next.js server process instead of proxying through
FastAPI, which keeps stored annotations browsable when MongoDB is reachable and
FastAPI is offline.

## Scripts

- `npm run dev`: start the local frontend server.
- `npm run test`: run lightweight helper tests.
- `npm run lint`: run ESLint.
- `npm run build`: build the production app.

## Pages

- `/`: explains what the annotator does, how jobs work, and important limits.
- `/jobs`: shows backend health, submits annotation jobs, and polls the shared
  sequential queue.
- `/annotations`: searches Mongo-backed generated annotations, displays the
  current annotation, loads older versions on demand, and links back to `/jobs`
  for update runs.
