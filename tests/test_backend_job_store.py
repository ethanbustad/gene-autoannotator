from backend.job_store import JobStore


def test_creates_and_fetches_queued_job(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    request = {
        "profile": "tcruzi-clbrener",
        "organism": None,
        "strain": None,
        "locus": "TcCLB.503799.4",
        "name": None,
        "cache_dir": "./.cache",
        "output_dir": "gen_json",
        "allow_online_name_lookup": False,
        "refresh_gene_name_cache": False,
        "cache_supplied_name": False,
    }

    created = store.create_job(request)
    fetched = store.get_job(created["id"])

    assert created["status"] == "queued"
    assert fetched["id"] == created["id"]
    assert fetched["request"] == request
    assert fetched["result"] is None
    assert fetched["error"] is None
    assert fetched["created_at"] is not None
    assert fetched["started_at"] is None
    assert fetched["finished_at"] is None


def test_tracks_running_and_completed_job(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    created = store.create_job({"profile": "mtb-h37rv", "locus": "Rv0001"})
    result = {
        "annotation": {"gene_id": "Rv0001", "name": "dnaA"},
        "papers_used": ["123"],
        "all_papers": ["123", "456"],
        "output_path": "gen_json/gen_Rv0001.json",
        "cumulative_relevance": 0.9,
        "selection_mode": "target_relevance_reached",
    }

    store.mark_running(created["id"])
    running = store.get_job(created["id"])
    store.mark_completed(created["id"], result, output_path=result["output_path"])
    completed = store.get_job(created["id"])

    assert running["status"] == "running"
    assert running["started_at"] is not None
    assert completed["status"] == "completed"
    assert completed["result"] == result
    assert completed["output_path"] == "gen_json/gen_Rv0001.json"
    assert completed["finished_at"] is not None


def test_tracks_failed_job_error(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    created = store.create_job({"profile": "mtb-h37rv", "locus": "bad"})

    store.mark_running(created["id"])
    store.mark_failed(created["id"], "Invalid locus")
    failed = store.get_job(created["id"])

    assert failed["status"] == "failed"
    assert failed["error"] == "Invalid locus"
    assert failed["finished_at"] is not None
