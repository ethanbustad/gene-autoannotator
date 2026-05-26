import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from autoannotation import organisms

from .annotation_store import AnnotationStoreUnavailable, annotation_store_from_env
from .job_store import JobStore
from .runner import run_annotation_job
from .schemas import (
    AnnotationDetailResponse,
    AnnotationJobRequest,
    AnnotationSearchResponse,
    AnnotationVersionsResponse,
    JobCreateResponse,
    JobsListResponse,
    JobRecordResponse,
    ProfileResponse,
    ProfilesResponse,
    ValidationRequest,
)

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at import time.
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


DEFAULT_DB_PATH = Path("backend/jobs.sqlite3")
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def _profile_response(profile):
    return ProfileResponse(
        profile_id=profile.profile_id,
        canonical_name=profile.canonical_name,
        species_name=profile.species_name,
        strain=profile.strain,
        synonyms=list(profile.synonyms),
        species_synonyms=list(profile.species_synonyms),
        strain_synonyms=list(profile.strain_synonyms),
        locus_regex=profile.locus_regex,
    )


def create_app(
    *,
    job_store=None,
    annotation_store=None,
    run_job=run_annotation_job,
    run_jobs_inline=False,
    start_worker=True,
):
    store = job_store or JobStore(DEFAULT_DB_PATH)
    annotations = (
        annotation_store
        if annotation_store is not None
        else annotation_store_from_env()
    )
    worker_lock = threading.Lock()

    def persist_completed_annotation(job):
        try:
            annotations.save_completed_job(job)
            store.mark_annotation_persisted(job["id"])
        except AnnotationStoreUnavailable:
            store.mark_annotation_error(job["id"], "MONGO_URI is not configured")
        except Exception as exc:  # noqa: BLE001 - expose persistence failures on the job.
            store.mark_annotation_error(job["id"], str(exc))

    def drain_queue():
        with worker_lock:
            while True:
                job = store.claim_next_queued_job()
                if job is None:
                    return
                try:
                    request = AnnotationJobRequest(**job["request"])
                    result = run_job(request)
                    store.mark_step(job["id"], "saving_result")
                    output_path = result.get("output_path") if result else None
                    store.mark_completed(job["id"], result or {}, output_path=output_path)
                    completed_job = store.get_job(job["id"])
                    persist_completed_annotation(completed_job)
                except Exception as exc:  # noqa: BLE001 - API must persist job failures.
                    store.mark_failed(job["id"], str(exc))

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            store.mark_interrupted_running_jobs("Job interrupted by API restart")
            worker = threading.Thread(target=drain_queue, daemon=True)
            worker.start()
        yield

    app = FastAPI(title="Gene Autoannotator API", lifespan=lifespan)
    cors_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def resource_snapshot():
        try:
            import psutil
        except ImportError:
            return {"status": "unavailable", "message": "psutil is not installed"}

        process = psutil.Process(os.getpid())
        memory = process.memory_info()
        return {
            "status": "ok",
            "process_memory_mb": round(memory.rss / 1024 / 1024, 2),
            "process_cpu_percent": process.cpu_percent(interval=None),
        }

    @app.get("/health")
    def health():
        try:
            job_store_health = store.health()
        except Exception as exc:  # noqa: BLE001 - health reports failures.
            job_store_health = {"status": "unavailable", "message": str(exc)}

        try:
            annotation_health = annotations.health()
        except Exception as exc:  # noqa: BLE001 - health reports failures.
            annotation_health = {"status": "unavailable", "message": str(exc)}

        return {
            "status": "ok",
            "stores": {
                "jobs": job_store_health,
                "annotations": annotation_health,
            },
            "queue": store.queue_summary(),
            "resources": resource_snapshot(),
        }

    @app.get("/profiles", response_model=ProfilesResponse)
    def profiles():
        return {
            "profiles": [
                _profile_response(profile)
                for profile in organisms.PROFILES
            ]
        }

    @app.post("/validate")
    def validate_locus(request: ValidationRequest):
        if request.profile:
            result = organisms.validate_locus_request(
                profile_identifier=request.profile,
                locus=request.locus,
            )
        else:
            result = organisms.validate_locus_request(
                organism_identifier=request.organism,
                strain_identifier=request.strain,
                locus=request.locus,
            )
        return result.to_dict()

    @app.post(
        "/jobs",
        response_model=JobCreateResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_job(request: AnnotationJobRequest, background_tasks: BackgroundTasks):
        job = store.create_job(request.model_dump())
        if run_jobs_inline:
            drain_queue()
            job = store.get_job(job["id"])
        elif start_worker:
            background_tasks.add_task(drain_queue)
        return {"job_id": job["id"], "status": job["status"]}

    @app.get("/jobs", response_model=JobsListResponse)
    def list_jobs(order: str = "newest"):
        normalized_order = order if order in {"newest", "queue"} else "newest"
        return {
            "jobs": store.list_jobs(order=normalized_order),
            "queue": store.queue_summary(),
        }

    @app.delete("/jobs/history")
    def clear_jobs_history():
        return {"deleted": store.clear_finished_jobs()}

    @app.get("/jobs/{job_id}", response_model=JobRecordResponse)
    def get_job(job_id: str):
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/jobs/{job_id}/result")
    def get_job_result(job_id: str):
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["status"] != "completed":
            raise HTTPException(status_code=409, detail="Job is not completed")
        return job["result"]

    @app.get("/annotations/search", response_model=AnnotationSearchResponse)
    def search_annotations(query: str, limit: int = Query(default=20, ge=1, le=100)):
        try:
            matches = annotations.search(query, limit=limit)
        except Exception as exc:  # noqa: BLE001 - surface storage outages as 503s.
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"query": query, "matches": matches}

    @app.get("/annotations/{annotation_id}", response_model=AnnotationDetailResponse)
    def get_annotation(annotation_id: str):
        try:
            annotation = annotations.get(annotation_id)
        except Exception as exc:  # noqa: BLE001 - surface storage outages as 503s.
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if annotation is None:
            raise HTTPException(status_code=404, detail="Annotation not found")
        return annotation

    @app.get(
        "/annotations/{annotation_id}/versions",
        response_model=AnnotationVersionsResponse,
    )
    def get_annotation_versions(annotation_id: str):
        try:
            versions = annotations.get_versions(annotation_id)
        except Exception as exc:  # noqa: BLE001 - surface storage outages as 503s.
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if versions is None:
            raise HTTPException(status_code=404, detail="Annotation not found")
        return {"annotation_id": annotation_id, "versions": versions}

    return app


app = create_app()
