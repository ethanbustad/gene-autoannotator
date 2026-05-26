from fastapi.testclient import TestClient

from backend.api import create_app
from backend.job_store import JobStore


def test_health_endpoint(tmp_path):
    app = create_app(job_store=JobStore(tmp_path / "jobs.sqlite3"))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
