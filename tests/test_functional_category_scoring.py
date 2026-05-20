from compareannotations.functional_category import (
	GoOntology,
	functional_category_similarity,
	load_go_ontology,
	parse_go_obo,
)


GO_FIXTURE = """
[Term]
id: GO:0008150
name: biological_process
namespace: biological_process

[Term]
id: GO:0009987
name: cellular process
namespace: biological_process
is_a: GO:0008150 ! biological_process

[Term]
id: GO:0006259
name: DNA metabolic process
namespace: biological_process
is_a: GO:0009987 ! cellular process

[Term]
id: GO:0006260
name: DNA replication
namespace: biological_process
is_a: GO:0006259 ! DNA metabolic process
synonym: "DNA synthesis" EXACT []

[Term]
id: GO:0006270
name: DNA replication initiation
namespace: biological_process
is_a: GO:0006260 ! DNA replication

[Term]
id: GO:0006281
name: DNA repair
namespace: biological_process
is_a: GO:0006259 ! DNA metabolic process

[Term]
id: GO:0055085
name: transmembrane transport
namespace: biological_process
is_a: GO:0006810 ! transport

[Term]
id: GO:0006810
name: transport
namespace: biological_process
is_a: GO:0009987 ! cellular process

[Term]
id: GO:1904659
name: D-glucose transmembrane transport
namespace: biological_process
is_a: GO:0055085 ! transmembrane transport
relationship: part_of GO:0006810 ! transport

[Term]
id: GO:1234567
name: obsolete test process
namespace: biological_process
is_obsolete: true
synonym: "legacy process" EXACT []
"""


def fixture_ontology():
	return parse_go_obo(GO_FIXTURE.splitlines())


def test_generated_descendant_scores_high_against_trusted_umbrella_category():
	score = functional_category_similarity(
		'information pathways',
		['DNA replication/repair'],
	)

	assert score >= 0.9


def test_generated_ancestor_scores_partial_against_trusted_specific_category():
	score = functional_category_similarity(
		['DNA replication/repair'],
		'information pathways',
	)

	assert 0.5 <= score < 0.9


def test_multiple_generated_categories_match_cell_wall_umbrella():
	score = functional_category_similarity(
		['Cell wall and cell processes'],
		['Metal homeostasis', 'Stress response', 'Metal transport'],
	)

	assert score >= 0.85


def test_unmapped_categories_return_none_for_semantic_fallback():
	score = functional_category_similarity(
		'conserved hypotheticals',
		['uncharacterized protein family'],
	)

	assert score is None


def test_vague_generated_category_does_not_match_specific_trusted_category():
	score = functional_category_similarity(
		'lipid metabolism',
		['survival'],
	)

	assert score is None


def test_real_go_labels_map_through_loaded_ontology():
	score = functional_category_similarity(
		'DNA metabolic process',
		['DNA replication initiation'],
		ontology=fixture_ontology(),
	)

	assert score >= 0.9


def test_real_go_synonyms_map_through_loaded_ontology():
	score = functional_category_similarity(
		'DNA replication',
		['DNA synthesis'],
		ontology=fixture_ontology(),
	)

	assert score == 1.0


def test_go_ids_map_directly_through_loaded_ontology():
	score = functional_category_similarity(
		'GO:0006259',
		['GO:0006260'],
		ontology=fixture_ontology(),
	)

	assert score >= 0.9


def test_go_ids_embedded_in_labels_map_through_loaded_ontology():
	score = functional_category_similarity(
		'DNA metabolic process (GO:0006259)',
		['GO:0006260'],
		ontology=fixture_ontology(),
	)

	assert score >= 0.9


def test_go_ontology_can_load_from_obo_file(tmp_path):
	obo_path = tmp_path / 'go-basic.obo'
	obo_path.write_text(GO_FIXTURE)

	ontology = load_go_ontology(obo_path)
	score = functional_category_similarity(
		'DNA metabolic process',
		['DNA replication'],
		ontology=ontology,
	)

	assert score >= 0.9


def test_go_part_of_relationships_are_used_as_parent_edges():
	score = functional_category_similarity(
		'transport',
		['D-glucose transmembrane transport'],
		ontology=fixture_ontology(),
	)

	assert score >= 0.9


def test_obsolete_go_terms_are_not_mapped():
	score = functional_category_similarity(
		'legacy process',
		['DNA replication'],
		ontology=fixture_ontology(),
	)

	assert score is None


def test_curated_aliases_still_work_without_loaded_ontology():
	empty_ontology = GoOntology(parents={}, label_index={})

	score = functional_category_similarity(
		'information pathways',
		['DNA replication/repair'],
		ontology=empty_ontology,
	)

	assert score >= 0.9


def test_score_field_uses_functional_category_graph_without_semantic_models(monkeypatch):
	from compareannotations import core

	def fail_if_called(*args, **kwargs):
		raise AssertionError('semantic scorer should not be called for mapped functional categories')

	monkeypatch.setattr(core, 'trusted_coverage_similarity', fail_if_called)
	monkeypatch.setattr(core, 'embedded_similarity', fail_if_called)
	monkeypatch.setattr(core, 'llm_coverage_similarity', fail_if_called)
	monkeypatch.setattr(core, 'llm_similarity', fail_if_called)

	scores = core.score_field(
		'functional_category',
		{'functional_category': 'information pathways'},
		{'functional_category': ['DNA replication/repair']},
	)

	assert scores['coverage'] >= 0.9
	assert scores['embedding'] == scores['coverage']
	assert scores['llm'] == scores['coverage']


def test_score_field_falls_back_to_semantic_scoring_for_unmapped_categories(monkeypatch):
	from compareannotations import core

	monkeypatch.setattr(core, 'trusted_coverage_similarity', lambda trusted, generated: 0.5)
	monkeypatch.setattr(core, 'embedded_similarity', lambda trusted, generated: 0.25)
	monkeypatch.setattr(core, 'llm_coverage_similarity', lambda trusted, generated: 0.6)
	monkeypatch.setattr(core, 'llm_similarity', lambda trusted, generated: 0.4)

	scores = core.score_field(
		'functional_category',
		{'functional_category': 'conserved hypotheticals'},
		{'functional_category': ['uncharacterized protein family']},
	)

	assert scores['coverage'] == 0.5
	assert scores['embedding'] > 0.0
	assert scores['llm'] > 0.0
