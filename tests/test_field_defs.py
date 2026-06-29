import pytest

from autoannotation import field_defs
from autoannotation import organisms


def test_resolve_effective_fields_always_includes_defaults():
    profile = organisms.profile_from_mapping({
        'profile_id': 'minimal',
        'canonical_name': 'Minimal Organism',
        'species_name': 'Minimal species',
    })

    fields = field_defs.resolve_effective_fields(profile)
    keys = [field.key for field in fields]

    assert keys[:2] == ['function', 'functional_category']
    assert 'drug_susc_impact' not in keys


def test_mtb_profile_includes_optional_custom_fields():
    profile = organisms.resolve_profile('mtb-h37rv')

    fields = field_defs.resolve_effective_fields(profile)
    keys = {field.key for field in fields}

    assert profile.kegg_organism_code == 'mtu'
    assert 'function' in keys
    assert 'drug_susc_impact' in keys
    assert fields[0].ortholog_allowed is True


def test_ortholog_policy_clears_allowed_without_kegg_code():
    profile = organisms.profile_from_mapping({
        'profile_id': 'no-kegg',
        'canonical_name': 'No KEGG Organism',
        'species_name': 'No KEGG species',
        'custom_fields': [{
            'key': 'virulence_factor',
            'label': 'Virulence',
            'description': 'Virulence phenotype.',
            'type': 'string',
            'required': False,
            'inference_strategy': 'paper_llm',
            'ortholog_allowed': True,
        }],
    })

    fields = field_defs.resolve_effective_fields(profile)

    virulence = next(field for field in fields if field.key == 'virulence_factor')
    assert virulence.ortholog_allowed is False


def test_validate_custom_field_rejects_reserved_keys():
    with pytest.raises(ValueError, match='reserved'):
        field_defs.validate_custom_field(field_defs.AnnotationFieldDef(
            key='gene_id',
            label='Gene ID',
            description='duplicate',
            type='string',
            required=False,
            inference_strategy='paper_llm',
            ortholog_allowed=False,
        ))


def test_llm_schema_fields_includes_functional_category():
    profile = organisms.resolve_profile('mtb-h37rv')

    keys = {field.key for field in field_defs.llm_schema_fields(profile)}

    assert 'function' in keys
    assert 'functional_category' in keys
    assert 'drug_susc_impact' in keys


def test_default_field_ortholog_override_applies_to_resolve():
    profile = organisms.profile_from_mapping({
        'profile_id': 'ortholog-defaults',
        'canonical_name': 'Ortholog defaults',
        'species_name': 'Test species',
        'kegg_organism_code': 'mtu',
        'default_field_ortholog': {
            'function': False,
            'functional_category': True,
        },
    })

    fields = field_defs.resolve_effective_fields(profile)
    by_key = {field.key: field for field in fields}

    assert by_key['function'].ortholog_allowed is False
    assert by_key['functional_category'].ortholog_allowed is True


def test_profile_from_mapping_accepts_custom_fields():
    profile = organisms.profile_from_mapping({
        'profile_id': 'custom-org',
        'canonical_name': 'Custom Organism',
        'species_name': 'Custom species',
        'kegg_organism_code': 'msm',
        'custom_fields': [{
            'key': 'virulence_factor',
            'label': 'Virulence factor',
            'description': 'Contribution to virulence.',
            'type': 'string',
            'required': False,
            'inference_strategy': 'paper_llm',
            'ortholog_allowed': True,
        }],
    })

    assert profile.kegg_organism_code == 'msm'
    assert profile.custom_fields[0].key == 'virulence_factor'
    assert profile.custom_fields[0].ortholog_allowed is True
