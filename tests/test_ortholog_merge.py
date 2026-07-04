import json

from autoannotation import field_defs
from autoannotation import metadata
from autoannotation import organisms
from autoannotation.metadata import (
    attach_ortholog_metadata,
    build_ortholog_pass_metadata,
    find_fields_needing_ortholog,
    merge_ortholog_evidence,
)
from autoannotation.orthology import OrthologHit


def test_find_fields_needing_ortholog_selects_missing_paper_llm_fields():
    annotation = {
        'function': None,
        'functional_category': ['DNA replication'],
        'drug_susc_impact': None,
    }
    coverage = {
        'function': 'insufficient_evidence',
        'functional_category': 'supported',
        'drug_susc_impact': 'insufficient_evidence',
    }

    missing = find_fields_needing_ortholog(
        annotation,
        coverage,
        field_defs.REQUIRED_DEFAULT_FIELDS,
    )

    assert missing == ['function']


def test_find_fields_needing_ortholog_skips_non_ortholog_allowed_fields():
    annotation = {'function': None, 'functional_category': None}
    coverage = {
        'function': 'insufficient_evidence',
        'functional_category': 'insufficient_evidence',
    }

    missing = find_fields_needing_ortholog(
        annotation,
        coverage,
        field_defs.REQUIRED_DEFAULT_FIELDS,
    )

    assert missing == ['function']


def test_find_fields_needing_ortholog_includes_functional_category_when_enabled():
    annotation = {'function': 'DNA replication', 'functional_category': None}
    coverage = {
        'function': 'supported',
        'functional_category': 'insufficient_evidence',
    }
    fields = field_defs.resolve_effective_fields(
        organisms.profile_from_mapping({
            'profile_id': 'fc-ortholog',
            'canonical_name': 'FC ortholog',
            'species_name': 'Test species',
            'kegg_organism_code': 'mtu',
            'default_field_ortholog': {'functional_category': True},
        })
    )

    missing = find_fields_needing_ortholog(annotation, coverage, fields)

    assert missing == ['functional_category']


def test_merge_ortholog_evidence_fills_null_direct_fields_only():
    direct = {
        'gene_id': 'Rv0001',
        'function': None,
        'functional_category': ['DNA replication'],
        'annotation_metadata': {'field_coverage': {'function': 'insufficient_evidence'}},
        'annotation_notes': 'Direct evidence limited.',
    }
    ortholog = {
        'gene_id': 'MO_000001',
        'function': 'Initiates DNA replication in M. orygis.',
    }
    hit = OrthologHit(
        source_organism_code='mory',
        source_organism_name='Mycobacterium orygis',
        source_gene_id='MO_000001',
        source_gene_name='dnaA',
        score=507.0,
        lookup_source='kegg_ssdb',
    )

    merged, filled = merge_ortholog_evidence(
        direct,
        ortholog,
        ['function'],
        hit,
        target_gene_id='Rv0001',
        target_gene_name='dnaA',
    )

    assert filled == ['function']
    assert merged['function'] == ortholog['function']
    assert merged['functional_category'] == ['DNA replication']
    assert merged['annotation_metadata']['field_provenance']['function'] == 'ortholog_derived'
    assert merged['annotation_metadata']['review_flags']['function'] is True
    assert 'ortholog evidence' in merged['annotation_notes']


def test_merge_ortholog_evidence_preserves_non_null_direct_values():
    direct = {'function': 'Direct function statement.'}
    ortholog = {'function': 'Ortholog function statement.'}
    hit = OrthologHit(
        source_organism_code='mory',
        source_organism_name=None,
        source_gene_id='MO_000001',
        source_gene_name=None,
        score=507.0,
        lookup_source='kegg_ssdb',
    )

    merged, filled = merge_ortholog_evidence(
        direct,
        ortholog,
        ['function'],
        hit,
    )

    assert filled == []
    assert merged['function'] == 'Direct function statement.'


def test_attach_ortholog_metadata_adds_top_hit_and_pass_block():
    hit = OrthologHit(
        source_organism_code='mory',
        source_organism_name='Mycobacterium orygis',
        source_gene_id='MO_000001',
        source_gene_name='dnaA',
        score=507.0,
        lookup_source='kegg_ssdb',
    )
    annotation = {
        'gene_id': 'Rv0001',
        'annotation_metadata': {},
    }
    pass_meta = build_ortholog_pass_metadata(
        ran=False,
        skipped_reason='no_eligible_missing_fields',
    )

    updated = attach_ortholog_metadata(annotation, hit, pass_meta)

    assert updated['annotation_metadata']['ortholog_top_hit']['source_gene_id'] == 'MO_000001'
    assert updated['annotation_metadata']['ortholog_pass']['skipped_reason'] == (
        'no_eligible_missing_fields'
    )


def test_merge_ortholog_annotation_keeps_both_values():
    from autoannotation import metadata, orthology

    hit = orthology.OrthologHit(
        source_organism_code="mory", source_organism_name="Mycobacterium orygis",
        source_gene_id="MO_000001", source_gene_name="octT",
        score=2600.0, identity=0.62, lookup_source="kegg_ssdb",
    )
    direct = {
        "gene_id": "Rv0001", "name": "dnaA",
        "function": "target function text",
        "infection_impact": None,
        "annotation_metadata": {},
    }
    ortholog = {
        "function": "ortholog function text",
        "infection_impact": "ortholog infection text",
    }
    merged, filled = metadata.merge_ortholog_annotation(
        direct, ortholog, ["function", "infection_impact"], hit,
        target_gene_id="Rv0001", target_gene_name="dnaA",
    )

    # both present -> canonical value stays target, ortholog stored separately
    assert merged["function"] == "target function text"
    assert merged["annotation_metadata"]["field_provenance"]["function"] == "target_plus_ortholog"
    of = merged["annotation_metadata"]["ortholog_fields"]["function"]
    assert of["value"] == "ortholog function text"
    assert of["source_gene_id"] == "MO_000001"
    assert of["identity"] == 0.62

    # target empty -> canonical value becomes ortholog, provenance ortholog_derived
    assert merged["infection_impact"] == "ortholog infection text"
    assert merged["annotation_metadata"]["field_provenance"]["infection_impact"] == "ortholog_derived"

    assert set(filled) == {"function", "infection_impact"}
    assert merged["annotation_metadata"]["review_flags"]["function"] is True


def test_merge_ortholog_annotation_skips_empty_ortholog_values():
    from autoannotation import metadata, orthology

    hit = orthology.OrthologHit(
        source_organism_code="mory", source_organism_name="Mycobacterium orygis",
        source_gene_id="MO_1", source_gene_name=None,
        score=1.0, identity=0.5, lookup_source="kegg_ssdb",
    )
    direct = {"function": "target only", "infection_impact": None, "annotation_metadata": {}}
    ortholog = {"function": None, "infection_impact": None}
    merged, filled = metadata.merge_ortholog_annotation(
        direct, ortholog, ["function", "infection_impact"], hit,
        target_gene_id="Rv0001", target_gene_name="dnaA",
    )
    assert filled == []
    assert "ortholog_fields" not in merged["annotation_metadata"] or \
        merged["annotation_metadata"]["ortholog_fields"] == {}
    assert merged["function"] == "target only"
