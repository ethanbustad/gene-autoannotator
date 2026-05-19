import argparse
import json
import sys
import os


from autoannotation.autoannotation import get_gene_annotation

def main(gene, cache_dir='./.cache'):
    result = get_gene_annotation(gene, cache_dir=cache_dir)

    if result is None:
        return

    pmc_ids = result["pmc_ids"]
    used = result["used_ids"]
    parsed = result.get("gene_annotation")

    if parsed is None:
        if result.get("gene_distillation") is None:
            print(f"No annotation produced for {gene}")
            return
        parsed = json.loads(result["gene_distillation"])

    print(gene, json.dumps(parsed, indent=2))
    print(f"Number of papers used: {len(used)}")
    print(f"Selection mode: {result.get('selection_mode', 'unknown')}")

    output_dir = "gen_json"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"gen_{gene}.json")

    with open(output_path, "w") as f:
        json.dump(parsed, f, indent=2)

    return {
        "annotation": parsed,
        "papers_used": used,
        "all_papers": pmc_ids,
        "output_path": output_path
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=(
            'Utility for inferring gene information for a given gene from published literature '
            'using LLMs.'
        )
    )

    parser.add_argument('gene',
        help='The gene to gather and summarize information on. An Rv gene locus.',
    )

    parser.add_argument('-c', '--cache-dir',
        default='./.cache',
        help=(
            'The directory where paper contents should be written (and read from, if already '
            'present). Default is %(default)s.'
        )
    )

    args = parser.parse_args(sys.argv[1:])
    args_dict = vars(args)
    main(**args_dict)
