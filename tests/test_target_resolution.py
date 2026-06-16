from autoannotation import gene_names, targets


def test_resolves_builtin_locus_only_target():
    result = targets.resolve_annotation_target(
        profile_identifier="mtb-h37rv",
        organism_identifier=None,
        strain_identifier=None,
        locus="Rv0001",
        name=None,
        allow_online_name_lookup=False,
    )

    assert result.profile.profile_id == "mtb-h37rv"
    assert result.resolved_locus == "Rv0001"
    assert result.primary_identifier == "Rv0001"
    assert "missing_gene_name" in result.warnings


def test_resolves_ad_hoc_name_only_target():
    result = targets.resolve_annotation_target(
        profile_identifier=None,
        organism_identifier="Custom bacterium",
        strain_identifier="Lab A",
        locus=None,
        name="abc1",
        allow_online_name_lookup=False,
    )

    assert result.profile.profile_id.startswith("ad-hoc-")
    assert result.profile.canonical_name == "Custom bacterium Lab A"
    assert result.resolved_locus is None
    assert result.resolved_name == "abc1"
    assert result.primary_identifier == "abc1"
    assert "ad_hoc_profile" in result.warnings
    assert "missing_locus" in result.warnings


def test_rejects_target_without_name_or_locus():
    try:
        targets.resolve_annotation_target(
            profile_identifier=None,
            organism_identifier="Custom bacterium",
            strain_identifier=None,
            locus=None,
            name=None,
            allow_online_name_lookup=False,
        )
    except ValueError as exc:
        assert str(exc) == "name or locus is required"
    else:
        raise AssertionError("target resolution should reject empty identifiers")


def test_name_only_target_uses_resolved_locus_when_available(monkeypatch):
    def fake_resolve_locus(*args, **kwargs):
        return gene_names.GeneLocusLookupResult(
            locus="CUS_0001",
            source="test_source",
            confidence="clear",
        )

    monkeypatch.setattr(targets.gene_names, "resolve_locus_from_gene_name", fake_resolve_locus)

    result = targets.resolve_annotation_target(
        profile_identifier=None,
        organism_identifier="Custom bacterium",
        strain_identifier=None,
        locus=None,
        name="abc1",
        allow_online_name_lookup=True,
    )

    assert result.resolved_locus == "CUS_0001"
    assert result.primary_identifier == "CUS_0001"


def test_name_only_builtin_target_warns_when_resolved_locus_mismatches_schema(monkeypatch):
    def fake_resolve_locus(*args, **kwargs):
        return gene_names.GeneLocusLookupResult(
            locus="RJtmp_000001",
            source="test_source",
            confidence="clear",
        )

    monkeypatch.setattr(targets.gene_names, "resolve_locus_from_gene_name", fake_resolve_locus)

    result = targets.resolve_annotation_target(
        profile_identifier="mtb-h37rv",
        organism_identifier=None,
        strain_identifier=None,
        locus=None,
        name="abc1",
        allow_online_name_lookup=True,
    )

    assert result.resolved_locus == "RJtmp_000001"
    assert "locus_schema_mismatch" in result.warnings

    preflight = result.to_preflight_dict()
    assert preflight["valid"] is True
    assert {
        "code": "locus_schema_mismatch",
        "message": targets.TARGET_WARNING_MESSAGES["locus_schema_mismatch"],
    } in preflight["warnings"]


def test_ad_hoc_profile_id_is_stable_across_case_and_whitespace_differences():
    first = targets.resolve_annotation_target(
        profile_identifier=None,
        organism_identifier=" Custom   bacterium ",
        strain_identifier=" Lab   A ",
        locus=None,
        name="abc1",
        allow_online_name_lookup=False,
    )
    second = targets.resolve_annotation_target(
        profile_identifier=None,
        organism_identifier="custom bacterium",
        strain_identifier="lab a",
        locus=None,
        name="abc1",
        allow_online_name_lookup=False,
    )

    assert first.profile.profile_id == second.profile.profile_id
    assert first.profile.canonical_name == "Custom   bacterium Lab   A"
