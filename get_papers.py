import argparse
import pandas as pd
from autoannotation.pmc import PmcPaperManager
import math


def load_myco_df():
    df = pd.read_csv(
        "./Mycobacterium_tuberculosis_H37Rv_txt_v5.txt",
        sep="\t"
    )

    df = (
        df.loc[df["Feature"].eq("CDS"), :]
        .set_index("Locus", drop=True)
        .sort_index()
    )

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Fetch PMC IDs for a gene locus"
    )
    parser.add_argument("gene", help="Gene locus (e.g. Rv0001)")
    parser.add_argument("--cache", default="./.cache")

    args = parser.parse_args()

    # load annotation table
    mycobrowser_df = load_myco_df()

    if args.gene not in mycobrowser_df.index:
        raise KeyError(f"Gene not found: {args.gene}")

    name = mycobrowser_df.at[args.gene, "Name"]

    manager = PmcPaperManager(args.cache)
    pmc_ids = manager.get_pmc_ids(args.gene, name)

    pmc_scores = {}

    fails = 0
    passes = 0

    for pmc_id in pmc_ids:
        status = manager.is_relevant(pmc_id, args.gene, name)

        if status:
            passes += 1
        else:
            fails += 1 

        pmc_scores[pmc_id] = manager.relevance_score(pmc_id, args.gene, name)

    sorted_pmc_ids = sorted(
        pmc_scores,
        key=pmc_scores.get,
        reverse=True
    )

    k = 5

    print(f"Gene: {args.gene}")
    print(f"Name: {name}")
    print(f"Count: {len(pmc_ids)}")
    print(f"Top {k} PMC Ids by relevance")
    for pmc_id in sorted_pmc_ids[:k]:
        print(f"PMC {pmc_id}: {pmc_scores[pmc_id]:.3f}")
    print()
    print(f"Bottom {k} PMC Ids by relevance")
    for pmc_id in sorted_pmc_ids[-k:]:
        print(f"PMC {pmc_id}: {pmc_scores[pmc_id]:.3f}")
    print()
    print(f"Passes: {passes}")
    print(f"Fails: {fails}")

    papers_to_analyze = []
    cum_relevance = 0
    target_relevance = 4.0
    rank = 2

    for pmc_id in sorted_pmc_ids:
        if pmc_scores[pmc_id] < 0.1:
            continue
        cum_relevance += 2* pmc_scores[pmc_id] / math.log2(rank)
        papers_to_analyze.append(pmc_id)
        if cum_relevance > target_relevance:
            break
        rank += 1

    print(f"\nNumber of papers to analyze: {len(papers_to_analyze)}")
    print(f"Cum_relevance: {cum_relevance:.3f}\n")

    print(f"Papers to analyze: {manager.select_papers_to_analyze(pmc_ids, args.gene, name)}")
    #for pmc_id in papers_to_analyze:
    #    print(f"PMC_ID: {pmc_id} | {pmc_scores[pmc_id]}")
        

    """
    top_pmc_id = sorted_pmc_ids[0]
    top_abstract = manager.get_abstract(top_pmc_id)

    print()
    print(f"Top paper abstract (PMC{top_pmc_id}):")
    print("-" * 80)

    if top_abstract is not None:
        print(top_abstract)
    else:
        print("No abstract available.")
    #print("\n".join(pmc_relevance))
    """

if __name__ == "__main__":
    main()