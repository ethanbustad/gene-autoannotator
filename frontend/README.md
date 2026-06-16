# Gene Autoannotator Frontend

This [Next.js](https://nextjs.org) app is the web interface for the gene
autoannotator API. It has pages for usage guidance, queued job submission,
Mongo-backed profile management, and searching generated annotation history.

## Getting Started

Copy the example environment file and point it at the Python API:

```bash
cp .env.example .env.local
```

Then run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

The Python backend should be running separately on port `8000`. Browser API
calls go through the same-origin `/api/backend` proxy, so remote devices only
need to reach the frontend on port `3000`. If FastAPI is not on the same
machine as Next.js, set `BACKEND_API_BASE_URL` to its internal URL.

Set `MONGO_URI` in `.env.local` when you want the frontend's annotation search
and review routes to read stored generated annotations directly from MongoDB.
Profile management is proxied through FastAPI, so the backend also needs
`MONGO_URI` for creating, updating, or deleting saved user profiles.

## Scripts

- `npm run dev`: start the local frontend server.
- `npm run test`: run lightweight helper tests.
- `npm run lint`: run ESLint.
- `npm run build`: build the production app.

## Pages

- `/`: explains what the annotator does, how jobs work, and important limits.
- `/jobs`: shows backend health, submits annotation jobs, and polls the shared
  sequential queue. Jobs can use a saved profile or a custom organism plus a
  gene name, locus, or both.
- `/profiles`: lists built-in and Mongo-backed organism profiles, and creates,
  edits, or deletes saved user profiles for reuse in job submissions.
- `/annotations`: searches Mongo-backed generated annotations, displays the
  current annotation, loads older versions on demand, and links back to `/jobs`
  for update runs.
