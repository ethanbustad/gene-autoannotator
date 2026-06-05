import json

import pandas as pd

from autoannotation import autoannotation
from autoannotation.pmc import RelevanceRecord


GENE_JSON = json.dumps({
    "rv_id": "Rv0001",
    "name": "dnaA",
    "function": "Initiates DNA replication.",
    "functional_category": ["DNA replication"],
    "drug_susc_impact": "",
    "infection_impact": "",
    "essential_in_vitro": True,
    "essential_in_vivo": True,
    "annotation_notes": "Analyzed one paper with moderate support.",
})

TCRUZI_JSON = json.dumps({
    "gene_id": "TcCLB.503799.4",
    "name": "TcCLB.503799.4",
    "function": "Surface protein.",
    "functional_category": ["host interaction"],
    "drug_susc_impact": None,
    "infection_impact": "May affect infection.",
    "essential_in_vitro": None,
    "essential_in_vivo": None,
    "annotation_notes": "Analyzed one T. cruzi paper.",
})


class FakeLlmHandler:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir

    @staticmethod
    def json_regex_filter(gene_json, organism_profile=None):
        return True

    def get_llm_gene_info_json(
        self, gene_id, gene_name, info_text, model, section_type='abstract',
        organism_profile=None,
    ):
        assert section_type == 'abstract'
        if gene_id.startswith("TcCLB"):
            assert organism_profile.profile_id == "tcruzi-clbrener"
            return TCRUZI_JSON, 0.1
        return GENE_JSON, 0.1

    def get_llm_consensus_json(
        self, json1, json2, json3, model, section_type='abstract',
        organism_profile=None,
    ):
        assert section_type == 'abstract'
        if organism_profile and organism_profile.profile_id == "tcruzi-clbrener":
            return TCRUZI_JSON, 0.1
        return GENE_JSON, 0.1

    def get_llm_aggregate_json(
        self, json_responses, pmids, model, literature_context=None, relevance_scores=None,
        organism_profile=None,
    ):
        assert literature_context is not None
        assert "Papers selected for analysis" in literature_context
        assert relevance_scores is not None
        if organism_profile and organism_profile.profile_id == "tcruzi-clbrener":
            return TCRUZI_JSON, 0.1
        return GENE_JSON, 0.1

    def summarize_usage(self):
        return {
            "calls": 5,
            "cache_hits": 0,
            "known_input_tokens": 100,
            "known_output_tokens": 25,
            "known_total_tokens": 125,
            "usage_records_with_missing_tokens": 0,
            "by_role": {},
            "by_model": {},
        }


class FakePmcPaperManager:
    def __init__(self, cache_dir, organism_profile=None):
        self.cache_dir = cache_dir
        self.organism_profile = organism_profile

    def get_pmc_ids(self, gene, name):
        raise AssertionError("get_gene_annotation should consume ranked records directly")

    def get_ranked_papers(self, gene, name):
        if gene.startswith("TcCLB"):
            assert self.organism_profile.profile_id == "tcruzi-clbrener"
            return [
                RelevanceRecord(
                    pmc_id="2",
                    pmid="54321",
                    score=0.85,
                    retrieval_sources=["locus"],
                    title="TcCLB.503799.4 in Trypanosoma cruzi",
                    year=2021,
                    section_hits={},
                    evidence_flags={},
                    score_components={},
                    warnings=[],
                )
            ]
        return [
            RelevanceRecord(
                pmc_id="1",
                pmid="12345",
                score=0.8,
                retrieval_sources=["locus"],
                title="Rv0001 dnaA in Mycobacterium tuberculosis",
                year=2020,
                section_hits={},
                evidence_flags={},
                score_components={},
                warnings=[],
            )
        ]

    def save_gene_pmc_ids(self, gene, pmc_ids):
        self.saved_ids = pmc_ids

    def select_relevance_records(self, records, **kwargs):
        from autoannotation.pmc import PaperSelectionResult

        assert isinstance(records[0], RelevanceRecord)
        return PaperSelectionResult(
            selected_records=records,
            cumulative_relevance=1.6,
            selection_mode="all_eligible_limited_literature",
            eligible_count=1,
            total_retrieved=1,
        )

    def is_relevant(self, pmc_id, gene, name):
        raise AssertionError("ranked selection should replace the legacy hard relevance gate")

    def get_abstract(self, pmc_id):
        if pmc_id == "2":
            return "TcCLB.503799.4 is discussed in Trypanosoma cruzi."
        return "Rv0001 dnaA initiates replication in Mycobacterium tuberculosis."

    def get_results(self, pmc_id):
        return None

    def get_discussion(self, pmc_id):
        return None

    def get_pmid(self, pmc_id):
        return "12345"


def test_get_gene_annotation_consumes_ranked_relevance_records(monkeypatch):
    mycobrowser_df = pd.DataFrame([
        {"Feature": "CDS", "Locus": "Rv0001", "Name": "dnaA"}
    ])
    monkeypatch.setattr(
        autoannotation.organisms.gene_names.pd,
        "read_csv",
        lambda *args, **kwargs: mycobrowser_df,
    )
    monkeypatch.setattr(autoannotation.llms, "LlmHandler", FakeLlmHandler)
    monkeypatch.setattr(autoannotation.pmc, "PmcPaperManager", FakePmcPaperManager)

    result = autoannotation.get_gene_annotation("Rv0001")

    assert result["used_ids"] == ["1"]
    assert result["pmc_ids"] == ["1"]
    assert result["cumulative_relevance"] == 1.6
    assert result["selection_mode"] == "all_eligible_limited_literature"
    assert result["gene_annotation"]["annotation_metadata"]["literature"]["papers_analyzed"] == 1
    assert result["gene_annotation"]["annotation_metadata"]["llm_usage"]["known_total_tokens"] == 125
    assert result["gene_annotation"]["annotation_notes"]


def test_get_gene_annotation_accepts_tcruzi_profile_without_table(monkeypatch, tmp_path):
    monkeypatch.setattr(autoannotation.llms, "LlmHandler", FakeLlmHandler)
    monkeypatch.setattr(autoannotation.pmc, "PmcPaperManager", FakePmcPaperManager)

    result = autoannotation.get_gene_annotation(
        profile="tcruzi-clbrener",
        locus="TcCLB.503799.4",
        gene_name_cache_dir=tmp_path,
        allow_online_name_lookup=False,
    )

    assert result["used_ids"] == ["2"]
    assert result["pmc_ids"] == ["2"]
    assert result["gene_annotation"]["gene_id"] == "TcCLB.503799.4"
    metadata = result["gene_annotation"]["annotation_metadata"]
    assert metadata["profile_id"] == "tcruzi-clbrener"
    assert metadata["species_name"] == "Trypanosoma cruzi"
    assert metadata["gene_name_source"] == "locus_fallback"
