# Gene Autoannotator Frontend

This is a placeholder [Next.js](https://nextjs.org) app for the gene
autoannotator API. It is intentionally small for this first phase: the page
checks backend health and shows a non-submitting annotation form shell.

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
[http://localhost:8000](http://localhost:8000).

## Scripts

- `npm run dev`: start the local frontend server.
- `npm run lint`: run ESLint.
- `npm run build`: build the production app.

## Current Scope

The current page is only a connectivity placeholder. A later phase can wire the
form to `POST /jobs`, poll `GET /jobs/{job_id}`, and display completed
annotation JSON from `GET /jobs/{job_id}/result`.
