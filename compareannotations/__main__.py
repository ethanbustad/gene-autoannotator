
import argparse
import sys
import json
import logging

#import compareannotations

from . import core

def main(trusted, generated):
	trusted_data = core.load_json(trusted)
	generated_data = core.load_json(generated)

	report, score = core.compare(trusted_data, generated_data)

	print("\n=== TRUSTED ANNOTATION ===\n")
	print(json.dumps(report["trusted"], indent=2))

	print("\n=== GENERATED ANNOTATION ===\n")
	print(json.dumps(report["generated"], indent=2))

	print("\n=== COMPARISON REPORT ===\n")

	print(f"{len(report["trusted"])}: fields in trusted")
	print(f"{len(report["generated"])}: fields in generated")
	print(f"{len(report["exact_matches"])}: exact field matches")
	print(f"{len(report["missing"])}: missing fields")
	print(f"{len(report["extra"])}: extra fields")

	print(f"\nOverall Score: {score}\n")


	print("\n=== END OF REPORT ===\n")

	return score

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Compare gene annotations"
	)

	parser.add_argument("trusted", help="Path to trusted JSON annotation")
	parser.add_argument("generated", help="Path to generated JSON annotation")

	args = parser.parse_args(sys.argv[1:])
	args_dict = vars(args)

	main(**args_dict)
