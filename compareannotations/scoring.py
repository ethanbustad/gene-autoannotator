
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
prompt 1
qwen2.5:latest                     845dbda0ea48    4.7 GB gave zero for everything 1:30
llama3.1:latest                    46e0c10c039e    4.9 GB gave 0.5 for everything 1:07
gemma3:4b                          a2af6cc3eb7f    3.3 GB gave zero for everything 1:24
phi3:3.8b                          4f2222927938    2.2 GB gave one for everything 0:52
llama3.2:3b                        a80c4f17acd5    2.0 GB gave zero for everything 0:53
mistral:7b-instruct-v0.2-q3_K_M    6897f015d8dc    3.5 GB gave one for everything 2:49
gemma:2b                           b50d6c999e59    1.7 GB gave zero for everything 0:51

prompt 2
qwen2.5:latest                     845dbda0ea48    4.7 GB
llama3.1:latest                    46e0c10c039e    4.9 GB
gemma3:4b                          a2af6cc3eb7f    3.3 GB
phi3:3.8b                          4f2222927938    2.2 GB
llama3.2:3b                        a80c4f17acd5    2.0 GB
mistral:7b-instruct-v0.2-q3_K_M    6897f015d8dc    3.5 GB
gemma:2b                           b50d6c999e59    1.7 GB

"""
MODEL = "llama3.1:latest"

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
	prompt1 = """
	You are a strict evaluator of factual equivalence between two statements
	
	Focus ONLY on the concrete facts (numbers, dates, names, quantities, entities). 

	Respond with a float between 0.0 and 1.0

	Rules:
	If any key facts differ (even slightly), the score must be LOW (<0.2)
	If statements are mutually exclusive (cannot both be true), score = 0.0
	Ignore wording, grammar, or phrasing completely

	Scoring:
	1.0 = identical facts
	0.0 = contradiction, mutually exclusive or different facts
	0.2 - 0.8 = only if facts partially overlap

	Statements to compare:

	Statement A: {a}
	Statement B: {b}

	"""
	prompt = """
	You are a strict evaluator of factual equivalence between two statements

	Focus ONLY on the concrete facts (numbers, dates, names, quantities, entitires, etc)

	Rules:
	If any facts differ, even slightly, the score must be 0.0
	if statements are mutually exclusive (cannot both be true), the score must be 0.0
	Ignore wording, grammar, and phrasing completely
	Respond with 1.0 if the facts are the same

	ONLY respond with 1.0 or 0.0

	Statements to compare:

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












