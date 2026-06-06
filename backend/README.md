# Gene Autoannotator Backend

This directory contains the FastAPI wrapper around the existing Python annotator.
It does not replace the command-line workflow; it imports the existing CLI-level
`autoannotation.__main__.main(...)` function and exposes it through HTTP job
endpoints.

## Setup

Use the existing project virtual environment if available:

```bash
activatevenv
```

Or create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the existing annotator dependencies and the small web dependency set:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-web.txt
```

Run the API server:

```bash
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Check that it is reachable:

```bash
curl http://10.158.45.197:8000/health
```

Annotation history writes use MongoDB. Put your local connection string in the
project root `.env` file so completed backend jobs can be saved:

```bash
MONGO_URI=mongodb://localhost:27017/gene_autoannotator
```

The API will still start if MongoDB is unavailable, but `/health` will report
backend annotation storage as unavailable and completed jobs will record an
annotation storage warning until the connection is fixed.

The Next.js frontend reads stored annotations directly from MongoDB through its
own `/api/annotations/...` routes. Add the same `MONGO_URI` value to
`frontend/.env.local` so annotation search/review continues to work even when
this FastAPI process is offline.

The annotator's Ollama models can also be configured in `.env`. This is useful
when the backend sees a different model list than the original development
machine:

```bash
AUTOANNOTATION_MODEL_MODE=lite
AUTOANNOTATION_SUMMARY_MODELS=mistral:7b-instruct-v0.2-q3_K_M,llama3.2:3b,gemma3:4b
AUTOANNOTATION_CONSENSUS_MODEL=phi3:3.8b
AUTOANNOTATION_AGGREGATION_MODEL=gemma3:4b
```

If `OLLAMA_HOST` is set in the terminal where the CLI works, add the same value
to `.env` before restarting the backend.

## Real Annotation Requirements

The API still uses the same underlying annotation code. Real jobs require the
same local services, models, network access, and cache/output directories as the
terminal command, including Ollama and the configured LLM models.

## Endpoint Summary

- `GET /health`: API, SQLite job store, Mongo annotation store, queue, and
  process resource health.
- `GET /profiles`: configured organism profiles.
- `POST /validate`: validates an organism/profile and locus.
- `GET /jobs`: lists shared jobs with queue positions.
- `DELETE /jobs/history`: clears completed and failed job history while leaving
  queued and running jobs untouched.
- `POST /jobs`: creates an annotation job and returns a `job_id`. Jobs are
  persisted in SQLite and executed sequentially; only one job runs at a time.
- `GET /jobs/{job_id}`: returns job status and metadata.
- `GET /jobs/{job_id}/result`: returns completed annotation JSON.
- `GET /annotations/search?query=...`: searches current generated annotations through FastAPI; the Next.js UI uses its own direct MongoDB read route.
- `GET /annotations/{annotation_id}`: returns the current stored annotation through FastAPI; the Next.js UI uses its own direct MongoDB read route.
- `GET /annotations/{annotation_id}/versions`: returns older stored versions through FastAPI; the Next.js UI uses its own direct MongoDB read route.
