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
})


class FakeLlmHandler:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir

    @staticmethod
    def json_regex_filter(gene_json):
        return True

    def get_llm_gene_info_json(self, gene_id, gene_name, info_text, model):
        return GENE_JSON, 0.1

    def get_llm_consensus_json(self, json1, json2, json3, model):
        return GENE_JSON, 0.1

    def get_llm_aggregate_json(self, json_responses, pmids, model):
        return GENE_JSON, 0.1


class FakePmcPaperManager:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir

    def get_pmc_ids(self, gene, name):
        raise AssertionError("get_gene_annotation should consume ranked records directly")

    def get_ranked_papers(self, gene, name):
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

    def select_papers_to_analyze(self, records, gene, name, target_relevance=4.0, min_score=0.1):
        assert isinstance(records[0], RelevanceRecord)
        return ["1"], 1.6

    def is_relevant(self, pmc_id, gene, name):
        raise AssertionError("ranked selection should replace the legacy hard relevance gate")

    def get_abstract(self, pmc_id):
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
    monkeypatch.setattr(autoannotation.pd, "read_csv", lambda *args, **kwargs: mycobrowser_df)
    monkeypatch.setattr(autoannotation.llms, "LlmHandler", FakeLlmHandler)
    monkeypatch.setattr(autoannotation.pmc, "PmcPaperManager", FakePmcPaperManager)

    result = autoannotation.get_gene_annotation("Rv0001")

    assert result["used_ids"] == ["1"]
    assert result["pmc_ids"] == ["1"]
    assert result["cumulative_relevance"] == 1.6
