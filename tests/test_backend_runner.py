from backend.runner import run_annotation_job
from backend.schemas import AnnotationJobRequest


def test_runner_calls_existing_cli_main():
    captured = {}

    def fake_main(**kwargs):
        captured.update(kwargs)
        return {
            "annotation": {"gene_id": "TcCLB.503799.4"},
            "papers_used": ["1"],
            "all_papers": ["1"],
            "output_path": "gen_json/tcruzi-clbrener/gen_TcCLB.503799.4.json",
            "cumulative_relevance": 1.0,
            "selection_mode": "all_eligible_limited_literature",
        }

    request = AnnotationJobRequest(
        profile="tcruzi-clbrener",
        locus="TcCLB.503799.4",
        name="TcUBP1",
        allow_online_name_lookup=False,
        cache_supplied_name=True,
    )

    result = run_annotation_job(request, annotation_main=fake_main)

    assert captured == {
        "gene": None,
        "profile": "tcruzi-clbrener",
        "organism": None,
        "strain": None,
        "locus": "TcCLB.503799.4",
        "name": "TcUBP1",
        "cache_dir": "./.cache",
        "output_dir": "gen_json",
        "gene_name_cache": ".cache/gene_names",
        "no_online_name_lookup": True,
        "refresh_gene_name_cache": False,
        "cache_supplied_name": True,
    }
    assert result["annotation"]["gene_id"] == "TcCLB.503799.4"
    assert result["output_path"].endswith("gen_TcCLB.503799.4.json")
