
import json
import logging

from autoannotation.metadata import COMPARISON_IGNORE_FIELDS

from .metrics import (
	combine_similarity_scores,
	is_unknown,
	stringify_field_value,
	verbosity_length_ratio,
)
from .scoring import (
	embedded_similarity,
	field_values_equal,
	llm_coverage_similarity,
	llm_similarity,
	trusted_coverage_similarity,
)

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

def compare(trusted, generated):
	
	field_scores = {}

	ignored = []

	for key in trusted:
		if key in COMPARISON_IGNORE_FIELDS:
			ignored.append(key)
			continue

		trusted_val = trusted.get(key)

		if is_unknown(trusted_val):
			ignored.append(key)
			continue

		field_scores[key] = score_field(key, trusted, generated)

	missing = [key for key in trusted.keys() if key not in generated and key not in ignored]
	extra = list(set(generated.keys()) - set(trusted.keys()))

	avg_embed, avg_llm, avg_coverage = compute_average_scores(field_scores)

	report = {
		"trusted": trusted,
		"generated": generated,
		"ignored": ignored,
		"field_scores": field_scores,
		"missing": missing,
		"extra": extra,
		"exact_matches": [key for key, value in field_scores.items() if value["exact"] == 1 ],
		"avg_embed": avg_embed,
		"avg_llm": avg_llm,
		"avg_coverage": avg_coverage,
		"scoring_mode": "asymmetric_trusted_coverage",
	}

	overall_score = compute_overall_score(field_scores)

	return report, overall_score

EMBED_SCORE_WEIGHT = 0.3
LLM_SCORE_WEIGHT = 0.7

def compute_overall_score(field_scores):
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
		return 0.0, 0.0, 0.0
	
	embed_sum = 0.0
	llm_sum = 0.0
	coverage_sum = 0.0

	for score in field_scores.values():
		embed_sum += score["embedding"]
		llm_sum += score["llm"]
		coverage_sum += score["coverage"]

	return embed_sum / total, llm_sum / total, coverage_sum / total


def score_field(key, trusted, generated):
	
	scores = {
		"exact": 0,
		"coverage": 0.0,
		"embedding": 0.0,
		"llm": 0.0,
		"verbosity_length_ratio": 1.0,
		"missing": False
	}

	if key not in generated:
		scores["missing"] = True
		return scores

	trusted_val = trusted.get(key)
	generated_val = generated.get(key)

	if is_unknown(generated_val):
		scores["missing"] = True
		return scores

	if field_values_equal(trusted_val, generated_val):
		scores.update({
			"exact": 1,
			"coverage": 1.0,
			"embedding": 1.0,
			"llm": 1.0,
		})
		return scores

	length_ratio = verbosity_length_ratio(trusted_val, generated_val)
	scores["verbosity_length_ratio"] = round(length_ratio, 2)

	coverage_embed = trusted_coverage_similarity(trusted_val, generated_val)
	symmetric_embed = embedded_similarity(trusted_val, generated_val)
	scores["coverage"] = round(coverage_embed, 3)
	scores["embedding"] = round(
		combine_similarity_scores(coverage_embed, symmetric_embed, length_ratio),
		3,
	)

	coverage_llm = llm_coverage_similarity(
		stringify_field_value(trusted_val),
		stringify_field_value(generated_val),
	)
	symmetric_llm = llm_similarity(
		f"{key}: {trusted_val}",
		f"{key}: {generated_val}",
	)
	# LLM symmetric returns -1..1; clip for blending.
	symmetric_llm_clipped = float(max(0.0, min(1.0, symmetric_llm)))
	scores["llm"] = round(
		combine_similarity_scores(coverage_llm, symmetric_llm_clipped, length_ratio),
		3,
	)

	return scores

