import time

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.job_store import JobStore


def test_health_endpoint(tmp_path):
    app = create_app(job_store=JobStore(tmp_path / "jobs.sqlite3"))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["stores"]["jobs"]["status"] == "ok"
    assert "queue" in payload
    assert payload["resources"]["status"] == "ok"
    assert "cpu_percent" in payload["resources"]
    assert "memory_total_bytes" in payload["resources"]
    assert "memory_used_bytes" in payload["resources"]
    assert "memory_available_bytes" in payload["resources"]
    assert "memory_percent" in payload["resources"]


def test_cors_allows_local_frontend_origin(tmp_path):
    app = create_app(job_store=JobStore(tmp_path / "jobs.sqlite3"))
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_allows_private_network_frontend_origin(tmp_path):
    app = create_app(job_store=JobStore(tmp_path / "jobs.sqlite3"))
    client = TestClient(app)

    response = client.options(
        "/validate",
        headers={
            "Origin": "http://10.158.45.197:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://10.158.45.197:3000"


def test_profiles_endpoint_lists_configured_profiles(tmp_path):
    app = create_app(job_store=JobStore(tmp_path / "jobs.sqlite3"))
    client = TestClient(app)

    response = client.get("/profiles")

    assert response.status_code == 200
    profile_ids = {profile["profile_id"] for profile in response.json()["profiles"]}
    assert "mtb-h37rv" in profile_ids
    assert "tcruzi-clbrener" in profile_ids


def test_validate_endpoint_wraps_existing_locus_validation(tmp_path):
    app = create_app(job_store=JobStore(tmp_path / "jobs.sqlite3"))
    client = TestClient(app)

    response = client.post(
        "/validate",
        json={
            "organism": "Trypanosoma cruzi",
            "strain": "CL Brener",
            "locus": "TcCLB.506529.310",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["profile_id"] == "tcruzi-clbrener"


def test_job_submission_can_complete_inline_with_injected_runner(tmp_path):
    def fake_runner(request):
        return {
            "annotation": {"gene_id": request.locus, "name": request.name},
            "papers_used": ["1"],
            "all_papers": ["1", "2"],
            "output_path": f"gen_json/tcruzi-clbrener/gen_{request.locus}.json",
            "cumulative_relevance": 0.8,
            "selection_mode": "target_relevance_reached",
        }

    app = create_app(
        job_store=JobStore(tmp_path / "jobs.sqlite3"),
        run_job=fake_runner,
        run_jobs_inline=True,
    )
    client = TestClient(app)

    create_response = client.post(
        "/jobs",
        json={
            "profile": "tcruzi-clbrener",
            "locus": "TcCLB.503799.4",
            "name": "TcUBP1",
            "allow_online_name_lookup": False,
        },
    )
    job_id = create_response.json()["job_id"]
    status_response = client.get(f"/jobs/{job_id}")
    result_response = client.get(f"/jobs/{job_id}/result")

    assert create_response.status_code == 201
    assert create_response.json()["status"] == "completed"
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert result_response.status_code == 200
    assert result_response.json()["annotation"]["gene_id"] == "TcCLB.503799.4"


def test_result_endpoint_rejects_unfinished_jobs(tmp_path):
    app = create_app(
        job_store=JobStore(tmp_path / "jobs.sqlite3"),
        run_job=lambda request: {"annotation": {"gene_id": request.locus}},
        run_jobs_inline=False,
        start_worker=False,
    )
    client = TestClient(app)

    create_response = client.post(
        "/jobs",
        json={"profile": "mtb-h37rv", "locus": "Rv0001"},
    )
    job_id = create_response.json()["job_id"]
    result_response = client.get(f"/jobs/{job_id}/result")

    assert create_response.status_code == 201
    assert create_response.json()["status"] == "queued"
    assert result_response.status_code == 409
    assert result_response.json()["detail"] == "Job is not completed"


def test_startup_worker_drains_existing_queued_jobs(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    queued = store.create_job({"profile": "mtb-h37rv", "locus": "Rv0001"})
    app = create_app(
        job_store=store,
        run_job=lambda request: {"annotation": {"gene_id": request.locus}},
        start_worker=True,
    )

    with TestClient(app):
        for _ in range(50):
            job = store.get_job(queued["id"])
            if job["status"] == "completed":
                break
            time.sleep(0.02)

    assert store.get_job(queued["id"])["status"] == "completed"


def test_job_submission_rejects_conflicting_profile_and_organism(tmp_path):
    app = create_app(job_store=JobStore(tmp_path / "jobs.sqlite3"))
    client = TestClient(app)

    response = client.post(
        "/jobs",
        json={
            "profile": "mtb-h37rv",
            "organism": "Trypanosoma cruzi",
            "locus": "Rv0001",
        },
    )

    assert response.status_code == 422


def test_jobs_endpoint_lists_submitted_jobs_in_queue_order(tmp_path):
    app = create_app(
        job_store=JobStore(tmp_path / "jobs.sqlite3"),
        run_job=lambda request: {"annotation": {"gene_id": request.locus}},
        run_jobs_inline=False,
        start_worker=False,
    )
    client = TestClient(app)

    first = client.post(
        "/jobs",
        json={"profile": "mtb-h37rv", "locus": "Rv0001"},
    ).json()
    second = client.post(
        "/jobs",
        json={"profile": "mtb-h37rv", "locus": "Rv0002"},
    ).json()
    response = client.get("/jobs?order=queue")

    assert response.status_code == 200
    payload = response.json()
    assert [job["id"] for job in payload["jobs"]] == [
        first["job_id"],
        second["job_id"],
    ]
    assert payload["jobs"][0]["queue_position"] == 1
    assert payload["jobs"][1]["queue_position"] == 2
    assert payload["queue"]["queued"] == 2


def test_delete_jobs_history_clears_only_finished_jobs(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    app = create_app(
        job_store=store,
        run_job=lambda request: {"annotation": {"gene_id": request.locus}},
        run_jobs_inline=False,
        start_worker=False,
    )
    client = TestClient(app)
    completed = store.create_job({"profile": "mtb-h37rv", "locus": "Rv0001"})
    failed = store.create_job({"profile": "mtb-h37rv", "locus": "Rv0002"})
    queued = store.create_job({"profile": "mtb-h37rv", "locus": "Rv0003"})
    running = store.create_job({"profile": "mtb-h37rv", "locus": "Rv0004"})
    store.mark_completed(completed["id"], {"annotation": {"gene_id": "Rv0001"}})
    store.mark_failed(failed["id"], "bad paper")
    store.mark_running(running["id"])

    response = client.delete("/jobs/history")
    jobs_response = client.get("/jobs?order=queue")

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    remaining_ids = {job["id"] for job in jobs_response.json()["jobs"]}
    assert remaining_ids == {queued["id"], running["id"]}


def test_completed_job_is_saved_to_annotation_store(tmp_path):
    class FakeAnnotationStore:
        def __init__(self):
            self.saved_jobs = []

        def health(self):
            return {"status": "ok"}

        def save_completed_job(self, job):
            self.saved_jobs.append(job)
            return "mtb-h37rv:Rv0001"

    annotation_store = FakeAnnotationStore()

    def fake_runner(request):
        return {
            "annotation": {
                "gene_id": request.locus,
                "name": "dnaA",
                "annotation_metadata": {"generated_at": "2026-01-01T00:00:00Z"},
            },
            "output_path": "gen_json/gen_Rv0001.json",
        }

    app = create_app(
        job_store=JobStore(tmp_path / "jobs.sqlite3"),
        annotation_store=annotation_store,
        run_job=fake_runner,
        run_jobs_inline=True,
    )
    client = TestClient(app)

    response = client.post(
        "/jobs",
        json={"profile": "mtb-h37rv", "locus": "Rv0001"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "completed"
    assert len(annotation_store.saved_jobs) == 1
    assert annotation_store.saved_jobs[0]["request"]["locus"] == "Rv0001"


def test_annotation_persistence_failure_is_visible_on_completed_job(tmp_path):
    class FailingAnnotationStore:
        def health(self):
            return {"status": "ok"}

        def save_completed_job(self, job):
            raise RuntimeError("mongo write failed")

    app = create_app(
        job_store=JobStore(tmp_path / "jobs.sqlite3"),
        annotation_store=FailingAnnotationStore(),
        run_job=lambda request: {"annotation": {"gene_id": request.locus}},
        run_jobs_inline=True,
    )
    client = TestClient(app)

    create_response = client.post(
        "/jobs",
        json={"profile": "mtb-h37rv", "locus": "Rv0001"},
    )
    job_response = client.get(f"/jobs/{create_response.json()['job_id']}")

    assert job_response.json()["status"] == "completed"
    assert job_response.json()["annotation_persisted"] is False
    assert job_response.json()["annotation_error"] == "mongo write failed"


def test_annotation_endpoints_use_annotation_store(tmp_path):
    class FakeAnnotationStore:
        def health(self):
            return {"status": "ok"}

        def search(self, query, limit=20):
            assert query == "dnaA"
            assert limit == 20
            return [
                {
                    "id": "mtb-h37rv:Rv0001",
                    "profile_id": "mtb-h37rv",
                    "canonical_name": "Mycobacterium tuberculosis H37Rv",
                    "normalized_locus": "Rv0001",
                    "gene_name": "dnaA",
                    "generated_at": "2026-01-01T00:00:00Z",
                    "version_count": 1,
                }
            ]

        def get(self, annotation_id):
            if annotation_id != "mtb-h37rv:Rv0001":
                return None
            return {
                "id": annotation_id,
                "profile_id": "mtb-h37rv",
                "canonical_name": "Mycobacterium tuberculosis H37Rv",
                "normalized_locus": "Rv0001",
                "gene_name": "dnaA",
                "generated_at": "2026-01-01T00:00:00Z",
                "result": {"annotation": {"gene_id": "Rv0001"}},
                "version_count": 1,
            }

        def get_versions(self, annotation_id):
            assert annotation_id == "mtb-h37rv:Rv0001"
            return [
                {
                    "version_id": "old-version",
                    "generated_at": "2025-12-01T00:00:00Z",
                    "job_id": "old-job",
                }
            ]

    app = create_app(
        job_store=JobStore(tmp_path / "jobs.sqlite3"),
        annotation_store=FakeAnnotationStore(),
        start_worker=False,
    )
    client = TestClient(app)

    search_response = client.get("/annotations/search?query=dnaA")
    detail_response = client.get("/annotations/mtb-h37rv:Rv0001")
    versions_response = client.get("/annotations/mtb-h37rv:Rv0001/versions")

    assert search_response.status_code == 200
    assert search_response.json()["matches"][0]["gene_name"] == "dnaA"
    assert detail_response.status_code == 200
    assert detail_response.json()["result"]["annotation"]["gene_id"] == "Rv0001"
    assert versions_response.status_code == 200
    assert versions_response.json()["versions"][0]["version_id"] == "old-version"


def test_annotation_search_rejects_unbounded_limit(tmp_path):
    class FakeAnnotationStore:
        def health(self):
            return {"status": "ok"}

        def search(self, query, limit=20):
            return []

    app = create_app(
        job_store=JobStore(tmp_path / "jobs.sqlite3"),
        annotation_store=FakeAnnotationStore(),
        start_worker=False,
    )
    client = TestClient(app)

    response = client.get("/annotations/search?query=dnaA&limit=1000")

    assert response.status_code == 422


def test_annotation_search_reports_store_runtime_errors_as_unavailable(tmp_path):
    class FailingAnnotationStore:
        def health(self):
            return {"status": "unavailable"}

        def search(self, query, limit=20):
            raise RuntimeError("mongo server is unreachable")

    app = create_app(
        job_store=JobStore(tmp_path / "jobs.sqlite3"),
        annotation_store=FailingAnnotationStore(),
        start_worker=False,
    )
    client = TestClient(app)

    response = client.get("/annotations/search?query=dnaA")

    assert response.status_code == 503
    assert response.json()["detail"] == "mongo server is unreachable"
