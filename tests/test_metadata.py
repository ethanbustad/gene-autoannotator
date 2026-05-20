import json

from autoannotation import metadata
from autoannotation.pmc import RelevanceRecord


def make_record(pmc_id, score, warnings=None):
    return RelevanceRecord(
        pmc_id=pmc_id,
        pmid=f"PMID{pmc_id}",
        score=score,
        retrieval_sources=["locus"],
        title=f"Title {pmc_id}",
        year=2020,
        section_hits={},
        evidence_flags={},
        score_components={},
        warnings=warnings or [],
    )


def test_filter_eligible_records_excludes_low_score_and_excluded_species():
    records = [
        make_record("1", 0.8),
        make_record("2", 0.05),
        make_record("3", 0.7, warnings=["excluded_species"]),
    ]

    eligible = metadata.filter_eligible_records(records)

    assert [record.pmc_id for record in eligible] == ["1"]


def test_filter_eligible_records_excludes_target_organism_warnings():
    records = [
        make_record("1", 0.8),
        make_record("2", 0.8, warnings=["missing_target_organism"]),
        make_record("3", 0.8, warnings=["off_target_organism_dominant"]),
    ]

    eligible = metadata.filter_eligible_records(records)

    assert [record.pmc_id for record in eligible] == ["1"]


def test_merge_annotation_output_adds_metadata_and_preserves_notes():
    gene_json = json.dumps({
        "rv_id": "Rv0001",
        "name": "dnaA",
        "function": "test",
        "functional_category": ["DNA replication"],
        "drug_susc_impact": "",
        "infection_impact": "",
        "essential_in_vitro": True,
        "essential_in_vivo": True,
        "annotation_notes": "Analyzed five papers with strong support.",
    })
    annotation_metadata = {"selection_mode": "cumulative_relevance_budget"}

    merged = metadata.merge_annotation_output(
        gene_json,
        annotation_metadata,
        field_coverage={"function": "supported"},
    )

    assert merged["annotation_notes"] == "Analyzed five papers with strong support."
    assert merged["annotation_metadata"]["selection_mode"] == "cumulative_relevance_budget"
    assert merged["annotation_metadata"]["field_coverage"]["function"] == "supported"


def test_build_literature_context_mentions_selected_paper_count():
    ranked = [make_record(str(i), 0.9 - i * 0.1) for i in range(6)]
    selected = ranked[:3]

    context = metadata.build_literature_context_for_notes(
        ranked_records=ranked,
        selected_records=selected,
        selection_mode=metadata.SELECTION_MODE_BUDGET,
        eligible_count=6,
        cumulative_relevance=4.5,
        target_relevance=9.0,
        min_papers=5,
    )

    assert "Papers selected for analysis: 3" in context
    assert "PMC0" in context
    assert "annotation_notes" in context
