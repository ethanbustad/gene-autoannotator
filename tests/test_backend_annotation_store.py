from backend.annotation_store import InMemoryAnnotationStore


def test_annotation_store_versions_current_annotation_by_profile_and_locus():
    store = InMemoryAnnotationStore()
    first_job = {
        "id": "first-job",
        "request": {"profile": "mtb-h37rv", "locus": "Rv0001", "name": "dnaA"},
        "result": {
            "annotation": {
                "gene_id": "Rv0001",
                "name": "dnaA",
                "annotation_metadata": {"generated_at": "2026-01-01T00:00:00Z"},
            },
            "output_path": "gen_json/gen_Rv0001.json",
        },
        "output_path": "gen_json/gen_Rv0001.json",
        "finished_at": "2026-01-01T00:00:00Z",
    }
    second_job = {
        "id": "second-job",
        "request": {"organism": "M. tuberculosis", "strain": "H37Rv", "locus": "Rv0001"},
        "result": {
            "annotation": {
                "gene_id": "Rv0001",
                "name": "dnaA updated",
                "annotation_metadata": {"generated_at": "2026-02-01T00:00:00Z"},
            },
            "output_path": "gen_json/gen_Rv0001_v2.json",
        },
        "output_path": "gen_json/gen_Rv0001_v2.json",
        "finished_at": "2026-02-01T00:00:00Z",
    }

    annotation_id = store.save_completed_job(first_job)
    updated_id = store.save_completed_job(second_job)
    detail = store.get(annotation_id)
    versions = store.get_versions(annotation_id)
    matches = store.search("dnaA updated")

    assert annotation_id == "mtb-h37rv:Rv0001"
    assert updated_id == annotation_id
    assert detail["gene_name"] == "dnaA updated"
    assert detail["generated_at"] == "2026-02-01T00:00:00Z"
    assert detail["version_count"] == 1
    assert versions[0]["job_id"] == "first-job"
    assert versions[0]["gene_name"] == "dnaA"
    assert matches[0]["id"] == annotation_id


def test_annotation_store_search_returns_empty_list_for_miss():
    store = InMemoryAnnotationStore()

    assert store.search("missing") == []
