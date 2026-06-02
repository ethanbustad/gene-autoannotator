# Gene Autoannotator

Work-in-progress tooling for generating literature-backed gene annotation drafts. The project combines a Python annotation pipeline, a FastAPI job queue, a Next.js review UI, and comparison scripts for benchmarking generated JSON against trusted annotations.

Generated annotations are curator aids, not curated truth. The pipeline tries to expose evidence, paper selection, unknown fields, and limitations so a human can review the result.

## What It Does

1. Resolve an organism profile and locus.
2. Resolve a gene name from a supplied value, profile table, local cache, NCBI Gene, UniProt, or locus fallback.
3. Query PubMed Central by locus and, when available, gene name.
4. Download/cache PMC XML and extract abstract, results, and discussion text.
5. Score and select papers with organism/gene relevance rules.
6. Ask three Ollama models for section-level JSON summaries.
7. Ask a consensus model to reconcile each section.
8. Filter malformed or wrong-locus JSON.
9. Ask an aggregation model for the final gene-level annotation.
10. Attach metadata about paper selection, quality flags, field coverage, timings, and gene-name provenance.

Main generated fields are `gene_id`, `name`, `function`, `functional_category`, `drug_susc_impact`, `infection_impact`, `essential_in_vitro`, `essential_in_vivo`, `annotation_notes`, and `annotation_metadata`.

## Repo Map

- `autoannotation/`: core Python pipeline, organism profiles, PMC retrieval, LLM prompts, metadata, and CLI.
- `backend/`: FastAPI API, SQLite job queue, optional MongoDB annotation history/search, and in-process runner.
- `frontend/`: Next.js UI for job submission, queue monitoring, and annotation search/review.
- `compareannotations/`: trusted-vs-generated scoring tools using exact matching, GO/category graph logic, embeddings/NLI, and an Ollama judge.
- `tests/`: mostly deterministic unit/API tests; some model-style tests require local model dependencies.
- `gen_json/`, `trust_json/`, `test_json/`: generated examples, trusted annotation fixtures, and small comparison fixtures.
- `run_pipeline.py`: manual benchmark script for a fixed MTB gene list plus Google Sheets logging.
- `get_papers.py`: diagnostic CLI for paper retrieval/ranking without running LLM annotation.

## Dependencies

Runtime assumptions:

- Python 3.11+ recommended.
- Node.js/npm for the frontend.
- Internet access to NCBI Entrez/PubMed Central and optional UniProt lookup.
- Local Ollama with the configured annotation/comparison models pulled.
- SQLite for job queue state.
- MongoDB optional, only for annotation history/search in the web app.

Python install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-web.txt
pip install pandas cloudscraper
```

`run_pipeline.py` additionally requires Google client libraries and a local service-account credential file:

```bash
pip install google-auth google-api-python-client
```

The pinned requirement files may need cleanup as the project settles.

Frontend install:

```bash
cd frontend
npm install
cp .env.example .env.local
```

Ollama defaults:

```bash
ollama pull mistral-nemo:12b
ollama pull llama3:8b
ollama pull gemma3:12b
ollama pull phi4:14b
ollama pull qwen2.5:7b-instruct
```

For smaller annotation models:

```bash
export AUTOANNOTATION_MODEL_MODE=lite
ollama pull mistral:7b-instruct
ollama pull llama3.2:3b
ollama pull gemma3:4b
ollama pull phi3:3.8b
```

## Configuration

Useful environment variables:

- `AUTOANNOTATION_MODEL_MODE=performance|lite`
- `AUTOANNOTATION_SUMMARY_MODELS=model1,model2,model3`
- `AUTOANNOTATION_CONSENSUS_MODEL=model`
- `AUTOANNOTATION_AGGREGATION_MODEL=model`
- `OLLAMA_HOST=http://host:11434` when Ollama is not local.
- `MONGO_URI` or `MONGODB_URI` to enable annotation history/search.
- `BACKEND_API_BASE_URL=http://127.0.0.1:8000` for the Next.js proxy/server calls.
- `CORS_ORIGINS` and `CORS_ORIGIN_REGEX` for FastAPI browser access.
- `GO_BASIC_OBO_PATH=data/go-basic.obo` for richer functional-category comparison.

Local/generated assets:

- `.cache/` stores PMC text, parsed sections, LLM responses, and gene-name cache records.
- `gen_json/` stores generated annotation JSON.
- `backend/jobs.sqlite3` stores queued/completed web jobs and is ignored by git.
- `Mycobacterium_tuberculosis_H37Rv_txt_v5.txt` is referenced for MTB annotation-table gene names but is not committed.
- `creds/` is ignored and is only needed for the Google Sheets benchmark script.

## Usage

Validate a profile/locus:

```bash
python -m autoannotation.validate --profile mtb-h37rv --locus Rv0001
python -m autoannotation.validate --organism "Trypanosoma cruzi" --strain "CL Brener" --locus TcCLB.503799.4
```

Inspect paper retrieval/ranking:

```bash
python get_papers.py --profile mtb-h37rv --locus Rv0001 --json-out name_query_results.json
```

Generate one annotation from the CLI:

```bash
python -m autoannotation --profile mtb-h37rv --locus Rv0001
python -m autoannotation --profile tcruzi-clbrener --locus TcCLB.503799.4 --name TcUBP1
```

Run the backend:

```bash
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Run the frontend:

```bash
cd frontend
npm run dev
```

If developing through SSH port forwarding:

```bash
ssh -L 3000:127.0.0.1:3000 -L 8000:127.0.0.1:8000 user@server
```

Compare generated output to trusted JSON:

```bash
python -m compareannotations trust_json/trust_Rv0001.json gen_json/gen_Rv0001.json
```

Run tests:

```bash
pytest
cd frontend && npm test && npm run lint
```

Some comparison/model tests may need HuggingFace model downloads and local Ollama availability.

## Web API Summary

- `GET /health`: job store, annotation store, queue, and process resource status.
- `GET /profiles`: configured organism profiles.
- `POST /validate`: profile/organism/locus validation.
- `POST /jobs`: queue an annotation job.
- `GET /jobs?order=queue|newest`: list job history and queue summary.
- `DELETE /jobs/history`: clear completed/failed jobs only.
- `GET /jobs/{job_id}` and `/jobs/{job_id}/result`: job metadata/result.
- `GET /annotations/search?query=...`: search stored Mongo annotations.
- `GET /annotations/{annotation_id}` and `/versions`: current annotation and older versions.

## Current Limitations

- No authentication, authorization, rate limiting, job cancellation, retries, or queue size limits.
- Jobs run in the FastAPI process; this is not a durable worker system.
- Only one annotation job runs at a time.
- Web progress is coarse (`queued`, `running`, `saving_result`, `completed`, `failed`).
- API request paths such as `cache_dir` and `output_dir` are trusted server paths.
- MongoDB is optional; if unavailable, jobs can complete but annotation search/history will not work.
- Literature parsing handles common top-level PMC/JATS sections and may miss nested or unusual section layouts.
- Relevance scoring is heuristic and should be tuned with `get_papers.py` plus tests.
- LLM validation checks JSON shape and gene identity, not factual correctness.
- Comparison scoring is useful for benchmarking but depends on local ML/Ollama models and can be slow.
- Some local assets and credentials are intentionally not committed.

## Roadmap / WIP

Likely next improvements:

- A UI/page for adding and maintaining organism strain profiles.
- More precise job progress from the backend, ideally per paper/section/model step.
- Security around the job API, such as auth or a passcode-enforced queue.
- Safer path handling and deployment guidance before exposing the API beyond trusted users.
- Better separation of fast unit tests from model/integration tests.
- Requirement-file cleanup once the runtime dependency set stabilizes.
