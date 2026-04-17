
import argparse
import sys
import json
import logging

#import compareannotations

import compareannotations

def main(trusted, generated):
	trusted_data = compareannotations.load_json(trusted)
	generated_data = compareannotations.load_json(generated)

	result = compareannotations.compare(trusted_data, generated_data)

	print("\n=== Trusted Annotation ===\n")
	print(json.dumps(result["trusted"], indent=2))

	print("\n=== Generated Annotation ===\n")
	print(json.dumps(result["generated"], indent=2))

	return result

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Compare gene annotations"
	)

	parser.add_argument("trusted", help="Path to trusted JSON annotation")
	parser.add_argument("generated", help="Path to generated JSON annotation")

	args = parser.parse_args(sys.argv[1:])
	args_dict = vars(args)

	main(**args_dict)
