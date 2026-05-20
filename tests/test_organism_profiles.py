import json

import pytest

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
