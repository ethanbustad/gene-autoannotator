"""Graph-aware scoring for functional category annotations.

This is intentionally small and curated: it bridges the project's current
free-text category labels to representative GO terms, then scores by graph
relationship instead of sentence similarity.
"""

import re
from collections import deque


SAME_TERM_SCORE = 1.0
GENERATED_DESCENDANT_SCORE = 0.95
GENERATED_ANCESTOR_SCORE = 0.65
CLOSE_SIBLING_SCORE = 0.4

UNINFORMATIVE_SHARED_ANCESTORS = frozenset({
	'GO:0008150',  # biological_process
	'GO:0009987',  # cellular process
})

CATEGORY_ALIASES = {
	'information pathways': {'GO:0006259', 'GO:0006351', 'GO:0006412'},
	'dna replication repair': {'GO:0006260', 'GO:0006281'},
	'dna replication': {'GO:0006260'},
	'replication': {'GO:0006260'},
	'dna replication initiation': {'GO:0006270'},
	'initiation of chromosome replication': {'GO:0006270'},
	'initiator protein': {'GO:0006260'},
	'dna repair': {'GO:0006281'},
	'transcription': {'GO:0006351'},
	'translation': {'GO:0006412'},
	'protein synthesis': {'GO:0006412'},
	'growth regulation': {'GO:0040007'},
	'regulation': {'GO:0065007'},

	'cell wall and cell processes': {
		'GO:0071555',
		'GO:0006810',
		'GO:0055085',
		'GO:0006875',
		'GO:0006950',
	},
	'cell wall': {'GO:0071555'},
	'cell wall organization': {'GO:0071555'},
	'transport': {'GO:0006810'},
	'membrane transport': {'GO:0055085'},
	'transmembrane transport': {'GO:0055085'},
	'ion transport': {'GO:0006811'},
	'metal transport': {'GO:0000041'},
	'metal homeostasis': {'GO:0006875'},
	'copper homeostasis': {'GO:0055070'},
	'heavy metal efflux': {'GO:0000041'},
	'zinc efflux': {'GO:0071577'},

	'intermediary metabolism and respiration': {'GO:0008152', 'GO:0045333'},
	'metabolism': {'GO:0008152'},
	'respiration': {'GO:0045333'},
	'electron transport': {'GO:0022900'},
	'hypoxia response': {'GO:0001666'},

	'lipid metabolism': {'GO:0006629'},
	'biosynthesis': {'GO:0009058'},

	'stress response': {'GO:0006950'},
	'multi metal stress response': {'GO:0006950'},
	'virulence': {'GO:0009405'},
	'host pathogen interaction': {'GO:0030383'},
	'immune response': {'GO:0006955'},
	'latent infection': {'GO:0070265'},
}

GO_PARENTS = {
	'GO:0006270': {'GO:0006260'},
	'GO:0006260': {'GO:0006259'},
	'GO:0006281': {'GO:0006259'},
	'GO:0006259': {'GO:0009987'},
	'GO:0006351': {'GO:0009987'},
	'GO:0006412': {'GO:0009987'},
	'GO:0040007': {'GO:0009987'},
	'GO:0065007': {'GO:0008150'},

	'GO:0071555': {'GO:0009987'},
	'GO:0055085': {'GO:0006810'},
	'GO:0006811': {'GO:0006810'},
	'GO:0000041': {'GO:0006811'},
	'GO:0071577': {'GO:0000041'},
	'GO:0055070': {'GO:0006875'},
	'GO:0006875': {'GO:0009987'},
	'GO:0006810': {'GO:0009987'},

	'GO:0045333': {'GO:0008152'},
	'GO:0022900': {'GO:0045333'},
	'GO:0001666': {'GO:0006950'},
	'GO:0008152': {'GO:0008150'},
	'GO:0006629': {'GO:0008152'},
	'GO:0009058': {'GO:0008152'},

	'GO:0006950': {'GO:0008150'},
	'GO:0009405': {'GO:0006950'},
	'GO:0030383': {'GO:0009405'},
	'GO:0006955': {'GO:0008150'},
	'GO:0070265': {'GO:0008150'},
	'GO:0009987': {'GO:0008150'},
	'GO:0008150': set(),
}


def functional_category_similarity(trusted_value, generated_value):
	"""Return graph similarity for mapped categories, or None when fallback is needed."""
	trusted_groups = _mapped_category_groups(trusted_value)
	generated_groups = _mapped_category_groups(generated_value)

	if not trusted_groups or not generated_groups:
		return None

	scores = []
	for trusted_nodes in trusted_groups:
		best = max(
			_score_node_groups(trusted_nodes, generated_nodes)
			for generated_nodes in generated_groups
		)
		scores.append(best)

	return round(sum(scores) / len(scores), 3)


def _mapped_category_groups(value):
	groups = []
	for category in _iter_category_values(value):
		nodes = CATEGORY_ALIASES.get(_normalize_category(category))
		if nodes:
			groups.append(nodes)
	return groups


def _iter_category_values(value):
	if value is None:
		return
	if isinstance(value, list):
		for item in value:
			if item is not None:
				yield str(item)
		return
	yield str(value)


def _normalize_category(category):
	category = re.sub(r'\([^)]*pmid[^)]*\)', '', category, flags=re.IGNORECASE)
	category = re.sub(r'pmid:?\s*\d+', '', category, flags=re.IGNORECASE)
	category = category.lower()
	category = category.replace('&', ' and ')
	category = category.replace('/', ' ')
	category = category.replace('-', ' ')
	category = re.sub(r'[^a-z0-9]+', ' ', category)
	return ' '.join(category.split())


def _score_node_groups(trusted_nodes, generated_nodes):
	return max(
		_score_nodes(trusted_node, generated_node)
		for trusted_node in trusted_nodes
		for generated_node in generated_nodes
	)


def _score_nodes(trusted_node, generated_node):
	if trusted_node == generated_node:
		return SAME_TERM_SCORE

	generated_ancestors = _ancestor_distances(generated_node)
	if trusted_node in generated_ancestors:
		if trusted_node in UNINFORMATIVE_SHARED_ANCESTORS:
			return 0.0
		return GENERATED_DESCENDANT_SCORE

	trusted_ancestors = _ancestor_distances(trusted_node)
	if generated_node in trusted_ancestors:
		if generated_node in UNINFORMATIVE_SHARED_ANCESTORS:
			return 0.0
		return GENERATED_ANCESTOR_SCORE

	shared_ancestors = (
		set(trusted_ancestors.keys())
		& set(generated_ancestors.keys())
		- UNINFORMATIVE_SHARED_ANCESTORS
	)
	if shared_ancestors:
		return CLOSE_SIBLING_SCORE

	return 0.0


def _ancestor_distances(node):
	distances = {node: 0}
	queue = deque([node])

	while queue:
		current = queue.popleft()
		for parent in GO_PARENTS.get(current, set()):
			if parent in distances:
				continue
			distances[parent] = distances[current] + 1
			queue.append(parent)

	return distances
