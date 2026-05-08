
import json
import logging

from .scoring import is_exact_match, embedded_similarity, llm_similarity

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

FIELD_WEIGHTS = {
	"rv_id": 0.0,
	"name": 0.0,
	"function": 3.0,
	"infection_impact": 1.5
}

def load_json(path):

	with open(path, "r") as f:
		return json.load(f)

def is_unknown(v):
	return v is None or v == "" or v == "unknown" or v == "missing"

def compare(trusted, generated):
	
	field_scores = {}

	ignored = []

	for key in trusted:
		trusted_val = trusted.get(key)

		if is_unknown(trusted_val):
			ignored.append(key)
			continue

		field_scores[key] = score_field(key, trusted, generated)

	missing = [key for key in trusted.keys() if key not in generated and key not in ignored]
	extra = list(set(generated.keys()) - set(trusted.keys()))

	avg_embed, avg_llm = compute_average_scores(field_scores)

	report = {
		"trusted": trusted,
		"generated": generated,
		"ignored": ignored,
		"field_scores": field_scores,
		"missing": missing,
		"extra": extra,
		"exact_matches": [key for key, value in field_scores.items() if value["exact"] == 1 ],
		"avg_embed": avg_embed,
		"avg_llm": avg_llm
	}

	overall_score = compute_overall_score(field_scores)

	return report, overall_score

EMBED_SCORE_WEIGHT = 0.3
LLM_SCORE_WEIGHT = 0.7

def compute_overall_score(field_scores):
	"""
	total = len(field_scores)
	if total == 0:
		return 0.0
	
	score_sum = 0.0

	for score in field_scores.values():
		if score["exact"] == 1:
			score_sum += 1.0
		else:
			score_sum += (EMBED_SCORE_WEIGHT * score["embedding"] + LLM_SCORE_WEIGHT * score["llm"])

	return score_sum / total
	"""
	weighted_score_sum = 0.0
	weight_sum = 0.0

	for key, score in field_scores.items():
		field_weight = FIELD_WEIGHTS.get(key, 1.0)

		if field_weight == 0:
			continue

		if score["exact"] == 1:
			field_score = 1.0
		else:
			field_score = (
				EMBED_SCORE_WEIGHT * score["embedding"] + LLM_SCORE_WEIGHT * score["llm"]
			)

		weighted_score_sum += (field_weight * field_score)

		weight_sum += field_weight

	if weight_sum == 0:
		return 0.0

	return weighted_score_sum / weight_sum

def compute_average_scores(field_scores):
	total = len(field_scores)
	if total == 0:
		return 0.0, 0.0
	
	embed_sum = 0.0
	llm_sum = 0.0

	for score in field_scores.values():
		embed_sum += score["embedding"]
		llm_sum += score["llm"]

	return embed_sum / total, llm_sum / total


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
	scores["llm"] = llm_similarity(f"{key}: {trusted_val}", f"{key}: {generated_val}")

	return scores


