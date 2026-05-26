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
curl http://localhost:8000/health
```

## Real Annotation Requirements

The API still uses the same underlying annotation code. Real jobs require the
same local services, models, network access, and cache/output directories as the
terminal command, including Ollama and the configured LLM models.

## Endpoint Summary

- `GET /health`: API health check.
- `GET /profiles`: configured organism profiles.
- `POST /validate`: validates an organism/profile and locus.
- `POST /jobs`: creates an annotation job and returns a `job_id`.
- `GET /jobs/{job_id}`: returns job status and metadata.
- `GET /jobs/{job_id}/result`: returns completed annotation JSON.
