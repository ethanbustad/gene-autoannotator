# Gene Autoannotator Frontend

This [Next.js](https://nextjs.org) app is the web interface for the gene
autoannotator API. It has pages for usage guidance, queued job submission, and
searching generated annotation history.

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

The Python backend should be running separately, usually at
[http://10.158.45.197:8000](http://10.158.45.197:8000).

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
