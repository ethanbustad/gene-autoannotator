import json

from autoannotation import llms
from autoannotation import metadata
from autoannotation import organisms


def _ad_hoc_profile_without_locus_regex():
    return organisms.OrganismProfile(
        profile_id='custom',
        canonical_name='Custom organism',
        species_name='Custom organism',
        strain=None,
        synonyms=(),
        species_synonyms=(),
        strain_synonyms=(),
        locus_regex='',
        search_terms=('Custom organism',),
    )


def test_is_unknown_value_treats_null_empty_and_placeholders():
    assert llms.is_unknown_value(None)
    assert llms.is_unknown_value('')
    assert llms.is_unknown_value('unknown')
    assert llms.is_unknown_value([])
    assert not llms.is_unknown_value('DNA replication initiator')
    assert not llms.is_unknown_value(['virulence'])


def test_normalize_annotation_fields_maps_placeholders_to_null():
    raw = {
        'rv_id': 'Rv0001',
        'name': 'dnaA',
        'function': 'Initiates replication.',
        'functional_category': [],
        'drug_susc_impact': 'n/a',
        'infection_impact': '',
        'essential_in_vitro': None,
        'essential_in_vivo': True,
    }

    normalized = llms.normalize_annotation_fields(raw)

    assert normalized['function'] == 'Initiates replication.'
    assert normalized['functional_category'] is None
    assert normalized['drug_susc_impact'] is None
    assert normalized['infection_impact'] is None
    assert normalized['essential_in_vitro'] is None
    assert normalized['essential_in_vivo'] is True


def test_json_regex_filter_accepts_partial_section_json():
    section_json = json.dumps({
        'rv_id': 'Rv0001',
        'name': 'dnaA',
        'function': 'Binds oriC.',
        'drug_susc_impact': None,
    })

    assert llms.LlmHandler.json_regex_filter(section_json)


def test_json_regex_filter_accepts_tcruzi_gene_id_for_profile():
    section_json = json.dumps({
        'gene_id': 'TcCLB.503799.4',
        'name': 'TcCLB.503799.4',
        'function': 'Surface protein.',
    })

    assert llms.LlmHandler.json_regex_filter(
        section_json,
        organism_profile=organisms.resolve_profile('tcruzi-clbrener'),
    )


def test_json_regex_filter_accepts_tcruzi_hyphenated_gene_name():
    section_json = json.dumps({
        'gene_id': 'TcCLB.503799.4',
        'name': 'trans-sialidase',
        'function': 'Surface protein.',
    })

    assert llms.LlmHandler.json_regex_filter(
        section_json,
        organism_profile=organisms.resolve_profile('tcruzi-clbrener'),
    )


def test_json_regex_filter_rejects_cross_profile_locus():
    section_json = json.dumps({
        'gene_id': 'Rv0001',
        'name': 'Rv0001',
        'function': 'DNA replication.',
    })

    assert not llms.LlmHandler.json_regex_filter(
        section_json,
        organism_profile=organisms.resolve_profile('tcruzi-clbrener'),
    )


def test_json_regex_filter_accepts_expected_gene_when_profile_lacks_locus_regex():
    section_json = json.dumps({
        'gene_id': 'CUS_001',
        'name': 'customA',
        'function': 'Custom function.',
    })

    assert llms.LlmHandler.json_regex_filter(
        section_json,
        organism_profile=_ad_hoc_profile_without_locus_regex(),
        expected_gene='CUS_001',
    )


def test_json_regex_filter_rejects_mismatching_expected_gene_without_locus_regex():
    section_json = json.dumps({
        'gene_id': 'CUS_002',
        'name': 'customA',
        'function': 'Custom function.',
    })

    assert not llms.LlmHandler.json_regex_filter(
        section_json,
        organism_profile=_ad_hoc_profile_without_locus_regex(),
        expected_gene='CUS_001',
    )


def test_section_prompt_uses_profile_organism_instead_of_mtb():
    captured = {}
    handler = llms.LlmHandler(cache_dir='./.cache')

    def fake_read_cache(model, prompt, json_schema):
        captured['prompt'] = prompt
        captured['schema'] = json_schema
        return json.dumps({
            'gene_id': 'TcCLB.503799.4',
            'name': 'TcCLB.503799.4',
        }), 0.1

    handler._read_cache = fake_read_cache

    response, _ = handler.get_llm_gene_info_json(
        'TcCLB.503799.4',
        'TcCLB.503799.4',
        'Trypanosoma cruzi text.',
        'fake-model',
        organism_profile=organisms.resolve_profile('tcruzi-clbrener'),
    )

    assert json.loads(response)['gene_id'] == 'TcCLB.503799.4'
    assert 'Trypanosoma cruzi CL Brener' in captured['prompt']
    assert 'Mycobacterium tuberculosis' not in captured['prompt']
    assert 'gene_id' in captured['schema']['properties']


def test_normalize_response_json_preserves_mtb_rv_id_for_legacy_outputs():
    handler = llms.LlmHandler(cache_dir='./.cache')

    normalized = json.loads(handler.normalize_response_json(
        json.dumps({
            'gene_id': 'Rv0001',
            'name': 'dnaA',
            'function': 'Initiates replication.',
        }),
        organism_profile=organisms.resolve_profile('mtb-h37rv'),
    ))

    assert normalized['gene_id'] == 'Rv0001'
    assert normalized['rv_id'] == 'Rv0001'


def test_build_field_coverage_marks_null_as_insufficient():
    coverage = metadata.build_field_coverage({
        'function': 'Known function.',
        'functional_category': ['DNA replication'],
        'drug_susc_impact': None,
        'infection_impact': None,
        'essential_in_vitro': None,
        'essential_in_vivo': True,
    })

    assert coverage['function'] == 'supported'
    assert coverage['drug_susc_impact'] == 'insufficient_evidence'
    assert coverage['essential_in_vivo'] == 'supported'
