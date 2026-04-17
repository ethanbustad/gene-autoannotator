

def is_exact_match(a, b):
	return " ".join(str(a).lower().split()) == " ".join(str(b).lower().split())

def embedded_similarity(trusted_field, generated_field):
	return 0.5

def llm_similarity(trusted_field, generated_field):
	return 0.5

