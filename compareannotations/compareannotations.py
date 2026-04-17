
import json
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

def load_json(path):

	with open(path, "r") as f:
		return json.load(f)

def compare(trusted, generated):
	return {
		"trusted": trusted,
		"generated": generated,
	}
