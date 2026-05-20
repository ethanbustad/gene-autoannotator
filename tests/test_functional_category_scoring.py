from compareannotations.functional_category import functional_category_similarity


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
