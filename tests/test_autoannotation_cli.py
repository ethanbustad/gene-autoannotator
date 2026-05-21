import json

import pytest

from autoannotation import __main__ as annotation_cli


def test_annotation_cli_namespaces_non_mtb_outputs(monkeypatch, tmp_path):
    captured = {}

    def fake_get_gene_annotation(**kwargs):
        captured.update(kwargs)
        return {
            "pmc_ids": ["1"],
            "used_ids": ["1"],
            "gene_annotation": {
                "gene_id": "TcCLB.503799.4",
                "name": "TcCLB.503799.4",
                "annotation_metadata": {"profile_id": "tcruzi-clbrener"},
            },
            "cumulative_relevance": 1.0,
            "selection_mode": "all_eligible_limited_literature",
        }

    monkeypatch.setattr(annotation_cli, "get_gene_annotation", fake_get_gene_annotation)

    result = annotation_cli.main(
        profile="tcruzi-clbrener",
        locus="TcCLB.503799.4",
        output_dir=str(tmp_path),
        no_online_name_lookup=True,
    )

    assert captured["profile"] == "tcruzi-clbrener"
    assert captured["locus"] == "TcCLB.503799.4"
    assert captured["allow_online_name_lookup"] is False
    assert result["output_path"].endswith(
        "tcruzi-clbrener/gen_TcCLB.503799.4.json"
    )
    payload = json.loads((tmp_path / "tcruzi-clbrener" / "gen_TcCLB.503799.4.json").read_text())
    assert payload["gene_id"] == "TcCLB.503799.4"


def test_annotation_cli_keeps_mtb_legacy_output_path(monkeypatch, tmp_path):
    def fake_get_gene_annotation(**kwargs):
        return {
            "pmc_ids": ["1"],
            "used_ids": ["1"],
            "gene_annotation": {
                "gene_id": "Rv0001",
                "rv_id": "Rv0001",
                "name": "dnaA",
                "annotation_metadata": {"profile_id": "mtb-h37rv"},
            },
            "cumulative_relevance": 1.0,
            "selection_mode": "all_eligible_limited_literature",
        }

    monkeypatch.setattr(annotation_cli, "get_gene_annotation", fake_get_gene_annotation)

    result = annotation_cli.main(gene="Rv0001", output_dir=str(tmp_path))

    assert result["output_path"].endswith("gen_Rv0001.json")
    assert (tmp_path / "gen_Rv0001.json").exists()


def test_annotation_cli_rejects_conflicting_profile_and_organism():
    with pytest.raises(ValueError):
        annotation_cli.main(
            profile="tcruzi-clbrener",
            organism="Mycobacterium tuberculosis",
            locus="TcCLB.503799.4",
        )


def test_annotation_cli_passes_gene_name_cache_controls(monkeypatch, tmp_path):
    captured = {}

    def fake_get_gene_annotation(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(annotation_cli, "get_gene_annotation", fake_get_gene_annotation)

    annotation_cli.main(
        gene="Rv0001",
        gene_name_cache=str(tmp_path / "names"),
        refresh_gene_name_cache=True,
    )

    assert captured["gene_name_cache_dir"] == str(tmp_path / "names")
    assert captured["allow_online_name_lookup"] is True
    assert captured["refresh_gene_name_cache"] is True


def test_annotation_cli_passes_cache_supplied_name_flag(monkeypatch):
    captured = {}

    def fake_get_gene_annotation(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(annotation_cli, "get_gene_annotation", fake_get_gene_annotation)

    annotation_cli.main(
        profile="tcruzi-clbrener",
        locus="TcCLB.507093.220",
        name="TcUBP1",
        cache_supplied_name=True,
    )

    assert captured["cache_supplied_name"] is True
