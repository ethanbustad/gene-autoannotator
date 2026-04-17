
import json
import logging

from compareannotations.scoring import is_exact_match, embedded_similarity, llm_similarity

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

def load_json(path):

	with open(path, "r") as f:
		return json.load(f)

def compare(trusted, generated):
	
	field_scores = {}

	for key in trusted:
		field_scores[key] = score_field(key, trusted, generated)

	missing = list(set(trusted.keys()) - set(generated.keys()))
	extra = list(set(generated.keys()) - set(trusted.keys()))

	report = {
		"trusted": trusted,
		"generated": generated,
		"field_scores": field_scores,
		"missing": missing,
		"extra": extra,
		"exact_matches": [key for key, value in field_scores.items() if value["exact"] == 1 ]
	}

	overall_score = compute_overall_score(field_scores)

	return report, overall_score

EMBED_SCORE_WEIGHT = 0.8
LLM_SCORE_WEIGHT = 0.8

def compute_overall_score(field_scores):
	total = len(field_scores)
	if total == 0:
		return 0.0
	
	score_sum = 0.0

	for score in field_scores.values():
		if score["exact"] == 1:
			score_sum += 1.0
		else:
			score_sum += EMBED_SCORE_WEIGHT * score["embedding"] + LLM_SCORE_WEIGHT * score["llm"]

	return score_sum / total


def score_field(key, trusted, generated):
	
	scores = {
		"exact": 0,
		"embedding": 0.0,
		"llm": 0.0,
		"missing": False
	}

	if key not in generated:
		scores["missing"] = True
		return scores

	trusted_val = trusted.get(key)
	generated_val = generated.get(key)

	if is_exact_match(trusted_val, generated_val):
		scores.update({"exact": 1, "embedding": 1.0, "llm": 1.0})
		return scores

	scores["embedding"] = embedded_similarity(trusted_val, generated_val)
	scores["llm"] = llm_similarity(trusted_val, generated_val)

	return scores


