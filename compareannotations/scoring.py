
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import pipeline
import numpy as np
import spacy
import re
import math

import ollama
import json

from .metrics import stringify_field_value

"""
qwen2.5:32b-instruct  20. GB  10:47 8/9
qwen2.5:14b-instruct  9.0 GB  0: /9
qwen2.5:7b-instruct   4.7 GB  02:53 9/9
qwen2.5:3b-instruct   1.9 GB  01:21 8/9
"""
MODEL = "qwen2.5:7b-instruct"

embedder = SentenceTransformer("all-mpnet-base-v2")

nli = pipeline("text-classification", model="roberta-large-mnli")

def is_exact_match(a, b):
	return " ".join(str(a).lower().split()) == " ".join(str(b).lower().split())


def field_values_equal(trusted_val, generated_val):
	if type(trusted_val) is bool or type(generated_val) is bool:
		return trusted_val == generated_val
	return is_exact_match(trusted_val, generated_val)


def _nli_pair(premise, hypothesis):
	return nli(f"{premise} </s></s> {hypothesis}")[0]


def trusted_coverage_similarity(trusted, generated):
	"""
	Asymmetric score: does generated cover the facts in trusted (0-1)?
	Higher when generated is a superset in meaning; not rewarded for extra length alone.
	"""
	trusted_s = stringify_field_value(trusted).strip()
	generated_s = stringify_field_value(generated).strip()

	if not trusted_s:
		return 1.0
	if not generated_s:
		return 0.0

	if field_values_equal(trusted, generated):
		return 1.0

	# Generated (premise) should entail trusted (hypothesis): trusted facts appear in generated.
	forward = _nli_pair(generated_s, trusted_s)
	label = forward['label']
	score = forward['score']

	if label == 'ENTAILMENT':
		coverage = float(np.clip(score, 0, 1))
	elif label == 'CONTRADICTION':
		coverage = float(np.clip(1 - score, 0, 1))
	else:
		emb = embedder.encode([trusted_s, generated_s])
		coverage = float(np.clip(cosine_similarity([emb[0]], [emb[1]])[0][0], 0, 1))

	# Penalize direct contradiction between trusted and generated statements.
	reverse = _nli_pair(trusted_s, generated_s)
	if reverse['label'] == 'CONTRADICTION':
		coverage *= float(np.clip(1 - reverse['score'] * 0.5, 0, 1))

	return coverage


def embedded_similarity(a, b):

	a = str(a)
	b = str(b)

	res = nli(f"{a} </s></s> {b}")[0]

	#print(f"a: {a}\nb: {b}\nres: {res}")

	label = res["label"]
	score = res["score"]

	emb = embedder.encode([a,b])
	sem_sim = cosine_similarity([emb[0]], [emb[1]])[0][0]

	if label == "ENTAILMENT":
		return float(np.clip(score, 0, 1))
	elif label == "CONTRADICTION":
	  return float(np.clip(1-score,0,1))

	return float(np.clip(sem_sim, 0, 1))


def llm_coverage_similarity(trusted, generated):
	prompt = f"""
  You are evaluating whether a GENERATED biological annotation field covers a TRUSTED
  reference field.

  Return ONLY a single float between 0.0 and 1.0.

  Scoring rules:
  1.0 = generated includes all key facts from trusted with no contradiction
  0.7 to 0.9 = generated includes trusted's main facts; minor wording differences OK
  0.3 to 0.6 = partial overlap; trusted has important facts missing from generated
  0.0 = unrelated, empty generated content, or generated contradicts trusted

  IMPORTANT:
  - Score coverage of trusted content only. Do NOT add points for extra details in generated
    that are absent from trusted.
  - Extra non-contradictory detail should not increase the score above 1.0 (cap mentally at 1.0).
  - If generated is longer but fully includes trusted, score high (0.85-1.0).
  - Penalize contradictions and major omissions.

  TRUSTED (reference): {trusted}
  GENERATED: {generated}
  """

	response = ollama.chat(
		model=MODEL,
		messages=[{'role': 'user', 'content': prompt}],
		format={
			'type': 'object',
			'properties': {
				'score': {'type': 'number'},
			},
			'required': ['score'],
		},
		options={'temperature': 0},
	)

	content = response['message']['content']
	raw = json.loads(content)['score']
	return float(np.clip(raw, 0, 1))


def llm_similarity(a, b):
  prompt = f"""
  You are evaluating factual agreement between two biological statements.

  Return ONLY a single float between -1.0 and 1.0.

  Scoring rules:
  1.0 = same factual claim
  0.7 to 0.9 = strongly overlapping facts
  0.3 to 0.6 = partially overlapping or related facts
  0.0 = unrelated or insufficient information
  -0.1 to -1.0 = contradictory or mutually exclusive claims

  IMPORTANT:
  - Only return a negative value for direct contradictions.
  - If uncertain, ambiguous, or partially related, bias toward a positive score.
  - Ignore wording, writing style, and phrasing completely.
  - Evaluate only factual content.

  Return ONLY the numeric score.

  Be conservative: default to a LOW score unless there is clear evidence the facts are equivalent.

  Compare statements by their core factual components:
  - entities
  - quantities
  - relationships
  - conditions (time, location, context)

  All key components must match for a high score.

  When comparing numerical values:
  
  - Be tolerant of small differences when they likely reflect approximation, measurement noise, or rounding.
  - Be strict when numbers define discrete, categorical, or identity-critical facts.
  - Do NOT be tolerant when small differences change category, count, or meaning.
  - Consider whether the difference changes the real-world implication. If it does, score low.
  
  Statement A: {a}
  Statement B: {b}
  """

  response = ollama.chat(
  model = MODEL,
  messages = [{"role": "user", "content": prompt}],
  format = {
    "type": "object",
    "properties": {
      "score": {"type": "number"}
    },
    "required": ["score"]
  },
  options = {"temperature": 0},
  )

  content = response["message"]["content"]
  return json.loads(content)["score"]












