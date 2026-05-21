import json

import get_papers
from autoannotation.pmc import PaperSelectionResult
from autoannotation.pmc import RelevanceRecord
from get_papers import summarize_ranked_records


def make_record(pmc_id, score, sources, warnings=None):
    return RelevanceRecord(
        pmc_id=pmc_id,
        pmid=f"PMID{pmc_id}",
        score=score,
        retrieval_sources=sources,
        title=f"Title {pmc_id}",
        year=2020,
        section_hits={},
        evidence_flags={},
        score_components={"component": score},
        warnings=warnings or [],
    )


def test_summarize_ranked_records_reports_counts_and_score_distribution():
    records = [
        make_record("1", 0.9, ["locus", "name"]),
        make_record("2", 0.55, ["name"], ["name_only_match"]),
        make_record("3", 0.05, ["name"], ["missing_organism"]),
    ]

    summary = summarize_ranked_records(records)

    assert summary["total"] == 3
    assert summary["retrieval_sources"]["locus"] == 1
    assert summary["retrieval_sources"]["name"] == 3
    assert summary["score"]["max"] == 0.9
    assert summary["score"]["min"] == 0.05
    assert summary["score"]["above_0_75"] == 1
    assert summary["score"]["above_0_50"] == 2
    assert summary["score"]["below_0_10"] == 1
    assert summary["warnings"]["name_only_match"] == 1
    assert summary["warnings"]["missing_organism"] == 1


def test_get_papers_cli_uses_tcruzi_profile_without_gene_table(monkeypatch, tmp_path):
    captured = {}

    class FakePmcPaperManager:
        def __init__(self, cache, organism_profile=None):
            captured["cache"] = cache
            captured["profile_id"] = organism_profile.profile_id

        def get_ranked_papers(self, gene, name):
            captured["gene"] = gene
            captured["name"] = name
            return [make_record("1", 0.9, ["locus"])]

        def select_relevance_records(self, records, **kwargs):
            return PaperSelectionResult(
                selected_records=records,
                cumulative_relevance=1.8,
                selection_mode="all_eligible_limited_literature",
                eligible_count=len(records),
                total_retrieved=len(records),
            )

    monkeypatch.setattr(get_papers, "PmcPaperManager", FakePmcPaperManager)
    output_path = tmp_path / "ranked.json"

    result = get_papers.main([
        "--profile",
        "tcruzi-clbrener",
        "--locus",
        "TcCLB.503799.4",
        "--no-online-name-lookup",
        "--gene-name-cache",
        str(tmp_path / "empty-gene-cache"),
        "--json-out",
        str(output_path),
    ])

    assert captured["profile_id"] == "tcruzi-clbrener"
    assert captured["gene"] == "TcCLB.503799.4"
    assert captured["name"] == "TcCLB.503799.4"
    assert result["profile_id"] == "tcruzi-clbrener"
    payload = json.loads(output_path.read_text())
    assert payload["profile_id"] == "tcruzi-clbrener"
    assert payload["gene_name_source"] == "locus_fallback"
    assert payload["gene_name_source_detail"]


def test_get_papers_cli_uses_gene_name_cache(monkeypatch, tmp_path):
    captured = {}

    class FakePmcPaperManager:
        def __init__(self, cache, organism_profile=None):
            captured["profile_id"] = organism_profile.profile_id

        def get_ranked_papers(self, gene, name):
            captured["gene"] = gene
            captured["name"] = name
            return [make_record("1", 0.9, ["name"])]

        def select_relevance_records(self, records, **kwargs):
            return PaperSelectionResult(
                selected_records=records,
                cumulative_relevance=1.8,
                selection_mode="all_eligible_limited_literature",
                eligible_count=len(records),
                total_retrieved=len(records),
            )

    monkeypatch.setattr(get_papers, "PmcPaperManager", FakePmcPaperManager)
    cache_dir = tmp_path / "gene_names"
    cache_dir.mkdir()
    (cache_dir / "tcruzi-clbrener.json").write_text(json.dumps({
        "TcCLB.507093.220": {
            "profile_id": "tcruzi-clbrener",
            "locus": "TcCLB.507093.220",
            "gene_name": "TcUBP1",
            "source": "manual_cache",
            "source_detail": "Curated from literature",
            "confidence": "curated",
            "aliases": [],
            "looked_up_at": "2026-05-20T00:00:00+00:00",
        }
    }))

    result = get_papers.main([
        "--profile",
        "tcruzi-clbrener",
        "--locus",
        "TcCLB.507093.220",
        "--gene-name-cache",
        str(cache_dir),
    ])

    assert captured["name"] == "TcUBP1"
    assert result["gene_name_source"] == "manual_cache"
    assert result["gene_name_source_detail"] == "Curated from literature"


def test_get_papers_cli_can_cache_supplied_name(monkeypatch, tmp_path):
    class FakePmcPaperManager:
        def __init__(self, cache, organism_profile=None):
            pass

        def get_ranked_papers(self, gene, name):
            return [make_record("1", 0.9, ["name"])]

        def select_relevance_records(self, records, **kwargs):
            return PaperSelectionResult(
                selected_records=records,
                cumulative_relevance=1.8,
                selection_mode="all_eligible_limited_literature",
                eligible_count=len(records),
                total_retrieved=len(records),
            )

    monkeypatch.setattr(get_papers, "PmcPaperManager", FakePmcPaperManager)

    get_papers.main([
        "--profile",
        "tcruzi-clbrener",
        "--locus",
        "TcCLB.507093.220",
        "--name",
        "TcUBP1",
        "--cache-supplied-name",
        "--gene-name-cache",
        str(tmp_path),
    ])

    payload = json.loads((tmp_path / "tcruzi-clbrener.json").read_text())
    record = payload["TcCLB.507093.220"]
    assert record["gene_name"] == "TcUBP1"
    assert record["source"] == "manual_cache"


def test_get_papers_cli_keeps_legacy_mtb_positional_gene(monkeypatch):
    captured = {}

    class FakePmcPaperManager:
        def __init__(self, cache, organism_profile=None):
            captured["profile_id"] = organism_profile.profile_id

        def get_ranked_papers(self, gene, name):
            captured["gene"] = gene
            captured["name"] = name
            return [make_record("1", 0.8, ["locus"])]

        def select_relevance_records(self, records, **kwargs):
            return PaperSelectionResult(
                selected_records=records,
                cumulative_relevance=1.6,
                selection_mode="all_eligible_limited_literature",
                eligible_count=len(records),
                total_retrieved=len(records),
            )

    monkeypatch.setattr(get_papers, "PmcPaperManager", FakePmcPaperManager)

    result = get_papers.main(["Rv0001"])

    assert captured["profile_id"] == "mtb-h37rv"
    assert captured["gene"] == "Rv0001"
    assert result["gene"] == "Rv0001"
