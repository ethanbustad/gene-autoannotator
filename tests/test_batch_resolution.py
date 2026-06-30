from autoannotation import batch_resolution, organisms


def test_resolve_batch_entry_locus_regex():
    profile = organisms.resolve_profile("mtb-h37rv")
    result = batch_resolution.resolve_batch_entry(
        profile,
        line=1,
        raw_input="Rv0001",
        submitted_locus="Rv0001",
        submitted_name=None,
        allow_online_name_lookup=False,
    )
    assert result["status"] == "ready"
    assert result["resolved_locus"] == "Rv0001"
    assert result["match_method"] == "locus_regex"


def test_resolve_batch_entry_name_via_table(monkeypatch):
    from autoannotation import gene_names

    profile = organisms.resolve_profile("mtb-h37rv")

    def fake_lookup(profile, gene_name):
        return gene_names.GeneLocusLookupResult(
            locus="Rv0001",
            source="annotation_table",
            confidence="profile_table",
        )

    monkeypatch.setattr(gene_names, "lookup_locus_from_annotation_table", fake_lookup)

    result = batch_resolution.resolve_batch_entry(
        profile,
        line=1,
        raw_input="dnaA",
        submitted_locus=None,
        submitted_name="dnaA",
        allow_online_name_lookup=False,
    )
    assert result["status"] == "ready"
    assert result["resolved_locus"] == "Rv0001"
    assert result["match_method"] == "annotation_table"


def test_resolve_batch_entry_supplied_pair():
    profile = organisms.resolve_profile("mtb-h37rv")
    result = batch_resolution.resolve_batch_entry(
        profile,
        line=1,
        raw_input="Rv0001,dnaA",
        submitted_locus="Rv0001",
        submitted_name="dnaA",
        allow_online_name_lookup=False,
    )
    assert result["status"] == "ready"
    assert result["match_method"] == "supplied_pair"


def test_apply_dedupe_marks_second_occurrence():
    entries = [
        {"status": "ready", "resolved_locus": "Rv0001", "resolved_name": "dnaA", "line": 1},
        {"status": "ready", "resolved_locus": "Rv0001", "resolved_name": "dnaA", "line": 2},
    ]
    deduped = batch_resolution.apply_deduplication(
        entries,
        profile_id="mtb-h37rv",
    )
    assert deduped[0]["status"] == "ready"
    assert deduped[1]["status"] == "duplicate_skipped"
