import json

import pandas as pd
import pytest

from autoannotation import gene_names
from autoannotation import organisms
from autoannotation import validate


def test_resolves_mtb_h37rv_synonyms_to_canonical_profile():
    profile = organisms.resolve_profile("mycobacteriumtuberculosish37rv")

    assert profile.profile_id == "mtb-h37rv"
    assert profile.canonical_name == "Mycobacterium tuberculosis H37Rv"


def test_rejects_unknown_organism_identifier():
    with pytest.raises(organisms.UnknownOrganismError):
        organisms.resolve_profile("mycobacterium tuberculosis h37ra")


def test_validates_locus_against_resolved_profile():
    result = organisms.validate_organism_locus("MTB H37Rv", "Rv0001")

    assert result.valid is True
    assert result.profile_id == "mtb-h37rv"
    assert result.canonical_name == "Mycobacterium tuberculosis H37Rv"
    assert result.normalized_locus == "Rv0001"


def test_rejects_locus_from_different_profile_schema():
    result = organisms.validate_organism_locus("mtb-h37rv", "RJtmp_000001")

    assert result.valid is False
    assert result.profile_id == "mtb-h37rv"
    assert result.reason == "locus_schema_mismatch"


def test_distinguishes_related_organism_profiles():
    result = organisms.validate_organism_locus("mycobacterium orygis 51145", "RJtmp_000001")

    assert result.valid is True
    assert result.profile_id == "morygis-51145"
    assert result.canonical_name == "Mycobacterium orygis 51145"


def test_infers_mtb_h37rv_profile_from_species_and_locus_schema():
    result = organisms.validate_locus_request(
        organism_identifier="Mycobacterium tuberculosis",
        locus="Rv0001",
    )

    assert result.valid is True
    assert result.profile_id == "mtb-h37rv"
    assert result.species_name == "Mycobacterium tuberculosis"
    assert result.strain == "H37Rv"


def test_species_abbreviation_can_infer_profile_from_locus_schema():
    result = organisms.validate_locus_request(
        organism_identifier="MTB",
        locus="Rv0001",
    )

    assert result.valid is True
    assert result.profile_id == "mtb-h37rv"


def test_species_locus_inference_rejects_other_species_schema():
    result = organisms.validate_locus_request(
        organism_identifier="Mycobacterium tuberculosis",
        locus="RJtmp_000001",
    )

    assert result.valid is False
    assert result.profile_id is None
    assert result.reason == "locus_schema_mismatch"


def test_strain_narrows_species_profile_resolution():
    result = organisms.validate_locus_request(
        organism_identifier="Mycobacterium tuberculosis",
        strain_identifier="H37Rv",
        locus="Rv0001",
    )

    assert result.valid is True
    assert result.profile_id == "mtb-h37rv"


def test_rejects_unknown_strain_for_known_species():
    result = organisms.validate_locus_request(
        organism_identifier="Mycobacterium tuberculosis",
        strain_identifier="H37Ra",
        locus="Rv0001",
    )

    assert result.valid is False
    assert result.reason == "unknown_strain"


def test_validates_mycobacterium_marinum_m_locus_schema():
    result = organisms.validate_locus_request(
        organism_identifier="Mycobacterium marinum",
        strain_identifier="M",
        locus="MMAR_0001",
    )

    assert result.valid is True
    assert result.profile_id == "mmarinum-m"


def test_validates_tcruzi_cl_brener_locus_schema():
    result = organisms.validate_locus_request(
        organism_identifier="T. cruzi",
        strain_identifier="CL Brener",
        locus="TcCLB.506529.310",
    )

    assert result.valid is True
    assert result.profile_id == "tcruzi-clbrener"


def test_validates_tcruzi_dm28c_locus_schema():
    result = organisms.validate_locus_request(
        organism_identifier="Trypanosoma cruzi",
        strain_identifier="Dm28c",
        locus="TCDM_13796",
    )

    assert result.valid is True
    assert result.profile_id == "tcruzi-dm28c"


def test_tcruzi_species_can_infer_strain_from_locus_schema():
    result = organisms.validate_locus_request(
        organism_identifier="Trypanosoma cruzi",
        locus="TcCLB.506529.310",
    )

    assert result.valid is True
    assert result.profile_id == "tcruzi-clbrener"


def test_resolve_gene_context_uses_mtb_annotation_table(monkeypatch):
    mycobrowser_df = pd.DataFrame([
        {"Feature": "CDS", "Locus": "Rv0001", "Name": "dnaA"}
    ])
    monkeypatch.setattr(gene_names.pd, "read_csv", lambda *args, **kwargs: mycobrowser_df)

    context = organisms.resolve_gene_context(
        profile_identifier="mtb-h37rv",
        locus="Rv0001",
        allow_online_name_lookup=False,
    )

    assert context.profile.profile_id == "mtb-h37rv"
    assert context.locus == "Rv0001"
    assert context.gene_name == "dnaA"
    assert context.gene_name_source == "annotation_table"


def test_resolve_gene_context_uses_supplied_name_before_table(monkeypatch):
    def fail_read_csv(*args, **kwargs):
        raise AssertionError("supplied name should avoid table lookup")

    monkeypatch.setattr(gene_names.pd, "read_csv", fail_read_csv)

    context = organisms.resolve_gene_context(
        profile_identifier="mtb-h37rv",
        locus="Rv0001",
        name="customName",
        allow_online_name_lookup=False,
    )

    assert context.gene_name == "customName"
    assert context.gene_name_source == "supplied"
    assert context.gene_name_source_detail == "supplied argument"


def test_resolve_gene_context_caches_supplied_name_when_requested(tmp_path):
    context = organisms.resolve_gene_context(
        profile_identifier="tcruzi-clbrener",
        locus="TcCLB.507093.220",
        name="TcUBP1",
        gene_name_cache_dir=tmp_path,
        cache_supplied_name=True,
        allow_online_name_lookup=False,
    )

    cached = gene_names.lookup_cached_gene_name(
        context.profile,
        "TcCLB.507093.220",
        tmp_path,
    )

    assert context.gene_name == "TcUBP1"
    assert context.gene_name_source == "supplied"
    assert cached.gene_name == "TcUBP1"
    assert cached.source == "manual_cache"
    assert cached.aliases == ["UBP1"]


def test_resolve_gene_context_allows_tcruzi_without_annotation_table(tmp_path):
    context = organisms.resolve_gene_context(
        profile_identifier="tcruzi-clbrener",
        locus="TcCLB.503799.4",
        gene_name_cache_dir=tmp_path,
        allow_online_name_lookup=False,
    )

    assert context.profile.profile_id == "tcruzi-clbrener"
    assert context.gene_name == "TcCLB.503799.4"
    assert context.gene_name_source == "locus_fallback"


def test_resolve_gene_context_uses_cached_gene_name(tmp_path):
    gene_names.write_cached_gene_name(
        gene_names.GeneNameRecord(
            profile_id="tcruzi-clbrener",
            locus="TcCLB.507093.220",
            gene_name="TcUBP1",
            source="manual_cache",
            source_detail="Curated from literature",
            confidence="curated",
            aliases=["UBP1"],
            looked_up_at="2026-05-20T00:00:00+00:00",
        ),
        tmp_path,
    )

    context = organisms.resolve_gene_context(
        profile_identifier="tcruzi-clbrener",
        locus="TcCLB.507093.220",
        gene_name_cache_dir=tmp_path,
        allow_online_name_lookup=False,
    )

    assert context.gene_name == "TcUBP1"
    assert context.gene_name_source == "manual_cache"
    assert context.gene_name_source_detail == "Curated from literature"
    assert context.gene_name_aliases == ["UBP1"]


def test_resolve_gene_context_uses_online_source_and_records_candidates(tmp_path):
    class FakeSource:
        def lookup(self, profile, locus):
            return gene_names.GeneNameLookupResult(
                gene_name="TcUBP1",
                source="ncbi_gene",
                source_detail="fake ncbi url",
                confidence="clear",
                aliases=["UBP1"],
            )

    context = organisms.resolve_gene_context(
        profile_identifier="tcruzi-clbrener",
        locus="TcCLB.507093.220",
        gene_name_cache_dir=tmp_path,
        allow_online_name_lookup=True,
        gene_name_sources=[FakeSource()],
    )

    assert context.gene_name == "TcUBP1"
    assert context.gene_name_source == "ncbi_gene"
    assert context.gene_name_source_detail == "fake ncbi url"
    assert context.gene_name_aliases == ["UBP1"]


def test_resolve_gene_context_rejects_invalid_locus_before_retrieval():
    with pytest.raises(organisms.InvalidLocusError):
        organisms.resolve_gene_context(
            profile_identifier="tcruzi-clbrener",
            locus="Rv0001",
            allow_online_name_lookup=False,
        )


def test_validate_cli_emits_json_for_success(capsys):
    exit_code = validate.main(["mtb-h37rv", "Rv0001"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["profile_id"] == "mtb-h37rv"


def test_validate_cli_returns_nonzero_for_invalid_locus(capsys):
    exit_code = validate.main(["mtb-h37rv", "RJtmp_000001"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert payload["reason"] == "locus_schema_mismatch"


def test_validate_cli_accepts_organism_and_locus_flags(capsys):
    exit_code = validate.main([
        "--organism",
        "Mycobacterium tuberculosis",
        "--locus",
        "Rv0001",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile_id"] == "mtb-h37rv"


def test_validate_cli_accepts_profile_and_locus_flags(capsys):
    exit_code = validate.main([
        "--profile",
        "mmarinum-m",
        "--locus",
        "MMAR_0001",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile_id"] == "mmarinum-m"
