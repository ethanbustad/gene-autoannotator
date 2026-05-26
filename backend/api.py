import threading
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, status

from autoannotation import organisms

from .job_store import JobStore
from .runner import run_annotation_job
from .schemas import (
    AnnotationJobRequest,
    JobCreateResponse,
    JobRecordResponse,
    ProfileResponse,
    ProfilesResponse,
    ValidationRequest,
)


DEFAULT_DB_PATH = Path("backend/jobs.sqlite3")


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
    run_job=run_annotation_job,
    run_jobs_inline=False,
    start_worker=True,
):
    app = FastAPI(title="Gene Autoannotator API")
    store = job_store or JobStore(DEFAULT_DB_PATH)
    worker_lock = threading.Lock()

    def execute_job(job_id):
        with worker_lock:
            try:
                job = store.get_job(job_id)
                if job is None:
                    return
                request = AnnotationJobRequest(**job["request"])
                store.mark_running(job_id)
                result = run_job(request)
                output_path = result.get("output_path") if result else None
                store.mark_completed(job_id, result or {}, output_path=output_path)
            except Exception as exc:  # noqa: BLE001 - API must persist job failures.
                store.mark_failed(job_id, str(exc))

    @app.get("/health")
    def health():
        return {"status": "ok"}

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
            execute_job(job["id"])
            job = store.get_job(job["id"])
        elif start_worker:
            background_tasks.add_task(execute_job, job["id"])
        return {"job_id": job["id"], "status": job["status"]}

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

    return app


app = create_app()
