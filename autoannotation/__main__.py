import argparse
import json
import sys

import autoannotation

def main(gene, cache_dir='./.cache'):
    gene_distillation = autoannotation.get_gene_annotation(gene, cache_dir=cache_dir)

    print(gene, json.dumps(gene_distillation, indent=2))

    return gene_distillation

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
