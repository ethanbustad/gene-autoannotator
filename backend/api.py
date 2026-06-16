import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from autoannotation import organisms, targets

from .annotation_store import AnnotationStoreUnavailable, annotation_store_from_env
from .job_store import JobStore
from .profile_store import (
    BuiltinAndUserProfileStore,
    DuplicateProfileError,
    InvalidProfileError,
    ProfileStoreUnavailable,
    user_profile_store_from_env,
)
from .runner import run_annotation_job
from .schemas import (
    AnnotationDetailResponse,
    AnnotationJobRequest,
    AnnotationSearchResponse,
    AnnotationVersionsResponse,
    JobCreateResponse,
    JobsListResponse,
    JobRecordResponse,
    ProfileDetailResponse,
    ProfilePayload,
    ProfilesResponse,
    ValidationRequest,
)

# FastAPI wrapper around the existing annotator. It is deliberately thin: jobs
# run in this Python process, SQLite stores queue state, and optional MongoDB
# storage keeps searchable annotation history.
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
DEFAULT_CORS_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|"
    r"127\.0\.0\.1|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
    r"):3000$"
)
PROFILE_CONFIG_FIELDS = (
    "profile_id",
    "canonical_name",
    "species_name",
    "strain",
    "synonyms",
    "species_synonyms",
    "strain_synonyms",
    "locus_regex",
    "search_terms",
    "target_patterns",
    "off_target_patterns",
    "excluded_species_patterns",
)


def create_app(
    *,
    job_store=None,
    annotation_store=None,
    profile_store=None,
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
    profiles_store = profile_store or BuiltinAndUserProfileStore(
        user_store=user_profile_store_from_env()
    )
    worker_lock = threading.Lock()

    def persist_completed_annotation(job):
        # Annotation history/search is a secondary persistence path. A Mongo
        # outage should be visible on the job but should not erase a completed
        # annotation result or mark the LLM run itself as failed.
        try:
            annotations.save_completed_job(job)
            store.mark_annotation_persisted(job["id"])
        except AnnotationStoreUnavailable:
            store.mark_annotation_error(job["id"], "MONGO_URI is not configured")
        except Exception as exc:  # noqa: BLE001 - expose persistence failures on the job.
            store.mark_annotation_error(job["id"], str(exc))

    def drain_queue():
        # One process-local drain loop is enough because JobStore also refuses
        # to claim a second running job. Multi-process deployments still need a
        # more explicit worker design before being treated as durable.
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
            # Running jobs cannot be resumed safely after an API restart because
            # the annotator is invoked in-process and has no checkpoint protocol.
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
    cors_origin_regex = os.getenv("CORS_ORIGIN_REGEX", DEFAULT_CORS_ORIGIN_REGEX).strip()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=cors_origin_regex or None,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def resource_snapshot():
        try:
            import psutil
        except ImportError:
            return {"status": "unavailable", "message": "psutil is not installed"}

        memory = psutil.virtual_memory()
        return {
            "status": "ok",
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_total_bytes": memory.total,
            "memory_used_bytes": memory.used,
            "memory_available_bytes": memory.available,
            "memory_percent": memory.percent,
        }

    def _profile_identifier_for_request(request):
        if request.profile or not request.organism or not request.locus:
            return request.profile
        result = organisms.validate_locus_request(
            organism_identifier=request.organism,
            strain_identifier=request.strain,
            locus=request.locus,
        )
        if result.valid and result.profile_id:
            return result.profile_id
        return None

    def _get_profile_for_target(profile_id):
        try:
            return profiles_store.get_profile(profile_id)
        except Exception as exc:  # noqa: BLE001 - profile storage failures are service outages.
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def _resolve_target_for_request(request):
        try:
            return targets.resolve_annotation_target(
                profile_identifier=_profile_identifier_for_request(request),
                organism_identifier=request.organism,
                strain_identifier=request.strain,
                locus=request.locus,
                name=request.name,
                profile_lookup=_get_profile_for_target if request.profile else None,
                allow_online_name_lookup=False,
                locus_regex=request.locus_regex,
                search_terms=request.search_terms,
                target_patterns=request.target_patterns,
                off_target_patterns=request.off_target_patterns,
                excluded_species_patterns=request.excluded_species_patterns,
            )
        except organisms.UnknownOrganismError as exc:
            raise HTTPException(status_code=404, detail="Profile not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _profile_config_from_target(target):
        config = {
            field: getattr(target.profile, field)
            for field in PROFILE_CONFIG_FIELDS
        }
        for field, value in config.items():
            if isinstance(value, tuple):
                config[field] = list(value)
        config["source"] = target.profile_source
        return config

    def _stored_request_for_target(request, target):
        stored_request = request.model_dump()
        if target.profile_source != "ad_hoc":
            stored_request["profile"] = target.profile.profile_id
            stored_request["organism"] = None
            stored_request["strain"] = None
        stored_request["target_preflight"] = target.to_preflight_dict()
        if request.profile or target.profile_source == "user":
            stored_request["profile_config"] = _profile_config_from_target(target)
        return stored_request

    def _reject_invalid_target(target):
        preflight = target.to_preflight_dict()
        if preflight["valid"]:
            return
        detail = next(
            (
                warning["message"]
                for warning in preflight["warnings"]
                if warning["code"] == targets.LOCUS_SCHEMA_MISMATCH
            ),
            "The target could not be submitted.",
        )
        raise HTTPException(status_code=422, detail=detail)

    def _public_job_record(job):
        public_job = dict(job)
        public_request = dict(public_job.get("request") or {})
        public_request.pop("profile_config", None)
        public_job["request"] = public_request
        return public_job

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

        try:
            profile_health = profiles_store.health()
        except Exception as exc:  # noqa: BLE001 - health reports failures.
            profile_health = {"status": "unavailable", "message": str(exc)}

        return {
            "status": "ok",
            "stores": {
                "jobs": job_store_health,
                "annotations": annotation_health,
                "profiles": profile_health,
            },
            "queue": store.queue_summary(),
            "resources": resource_snapshot(),
        }

    @app.get("/profiles", response_model=ProfilesResponse)
    def profiles():
        try:
            return {"profiles": profiles_store.list_profiles()}
        except Exception as exc:  # noqa: BLE001 - surface profile storage outages as 503s.
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post(
        "/profiles",
        response_model=ProfileDetailResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_profile(request: ProfilePayload):
        try:
            return profiles_store.create_user_profile(request.model_dump())
        except DuplicateProfileError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidProfileError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProfileStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/profiles/{profile_id}", response_model=ProfileDetailResponse)
    def get_profile(profile_id: str):
        try:
            profile = profiles_store.get_profile(profile_id)
        except Exception as exc:  # noqa: BLE001 - surface profile storage outages as 503s.
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile

    @app.put("/profiles/{profile_id}", response_model=ProfileDetailResponse)
    def update_profile(profile_id: str, request: ProfilePayload):
        try:
            profile = profiles_store.update_user_profile(profile_id, request.model_dump())
        except InvalidProfileError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProfileStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile

    @app.delete("/profiles/{profile_id}")
    def delete_profile(profile_id: str):
        try:
            deleted = profiles_store.delete_user_profile(profile_id)
        except InvalidProfileError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProfileStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"deleted": True}

    @app.post("/validate")
    def validate_locus(request: ValidationRequest):
        target = _resolve_target_for_request(request)
        return target.to_preflight_dict()

    @app.post(
        "/jobs",
        response_model=JobCreateResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_job(request: AnnotationJobRequest, background_tasks: BackgroundTasks):
        target = _resolve_target_for_request(request)
        _reject_invalid_target(target)
        stored_request = _stored_request_for_target(request, target)
        job = store.create_job(stored_request)
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
            "jobs": [
                _public_job_record(job)
                for job in store.list_jobs(order=normalized_order)
            ],
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
        return _public_job_record(job)

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
