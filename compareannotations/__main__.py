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

    print(f"{len(report["trusted"])}\t: fields in trusted")
    print(f"{len(report["generated"])}\t: fields in generated")
    print(f"{len(report['ignored'])}\t: ignored fields")
    print(f"{len(report["exact_matches"])}\t: exact field matches")
	
    non_exact = len(report["field_scores"]) - len(report["exact_matches"])
    print(f"{non_exact}\t: non-exact field Matches")

    print(f"{report["avg_embed"]:.2f}\t: AVG embed score")
    print(f"{report["avg_llm"]:.2f}\t: AVG llm score")

    print(f"{len(report["missing"])}\t: missing fields")
    print(f"{len(report["extra"])}\t: extra fields")

    print("\n=== FIELD SCORES ===\n")

    for field, scores in report["field_scores"].items():
        print(f"overall score: {(scores['embedding'] + scores['llm']) / 2:.2f} exact score: {scores['exact']} embed score: {scores['embedding']:.2f} llm score: {scores['llm']:.2f}\t: field: {field}")

    print(f"\nOverall Score: {score:.2f}\n")

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
