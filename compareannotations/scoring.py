
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import pipeline
import numpy as np
import spacy
import re
import math

import ollama
import json
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


def llm_similarity(a, b):
  prompt = f"""
  You are a strict evaluator of factual equivalence.

  Return ONLY a single float between 0.0 and 1.0

  1.0 = identical facts  
  0.0 = contradiction or different facts  
  Values in between = partial overlap  

  Ignore wording, grammar, and phrasing completely.

  Be conservative: default to a LOW score unless there is clear evidence the facts are equivalent.
  If any key fact differs, is missing, or is uncertain, score near 0.0.

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












