import argparse
from collections import Counter
import json
from autoannotation import gene_names
from autoannotation import targets
from autoannotation.pmc import (
    PmcPaperManager,
    DEFAULT_MAX_PAPERS,
    DEFAULT_MAX_RANK,
    DEFAULT_MIN_PAPERS,
    DEFAULT_MIN_SCORE,
    DEFAULT_TARGET_RELEVANCE,
)

# Diagnostic CLI for literature retrieval and ranking. Use this before changing
# relevance weights or organism patterns because it shows why papers would be
# selected without spending time on LLM inference.

def summarize_ranked_records(records):
    scores = [record.score for record in records]
    retrieval_sources = Counter(
        source
        for record in records
        for source in record.retrieval_sources
    )
    warnings = Counter(
        warning
        for record in records
        for warning in record.warnings
    )

    if not scores:
        score_summary = {
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "above_0_75": 0,
            "above_0_50": 0,
            "above_0_25": 0,
            "below_0_10": 0,
        }
    else:
        sorted_scores = sorted(scores)
        middle = len(sorted_scores) // 2
        if len(sorted_scores) % 2 == 0:
            median = (sorted_scores[middle - 1] + sorted_scores[middle]) / 2
        else:
            median = sorted_scores[middle]

        score_summary = {
            "min": round(min(scores), 3),
            "max": round(max(scores), 3),
            "mean": round(sum(scores) / len(scores), 3),
            "median": round(median, 3),
            "above_0_75": sum(score >= 0.75 for score in scores),
            "above_0_50": sum(score >= 0.50 for score in scores),
            "above_0_25": sum(score >= 0.25 for score in scores),
            "below_0_10": sum(score < 0.10 for score in scores),
        }

    return {
        "total": len(records),
        "retrieval_sources": dict(retrieval_sources),
        "warnings": dict(warnings),
        "score": score_summary,
    }

def relevance_record_to_dict(record):
    return {
        "pmc_id": record.pmc_id,
        "pmid": record.pmid,
        "score": record.score,
        "retrieval_sources": record.retrieval_sources,
        "title": record.title,
        "year": record.year,
        "section_hits": record.section_hits,
        "evidence_flags": record.evidence_flags,
        "score_components": record.score_components,
        "warnings": record.warnings,
    }

def format_record(record):
    sources = ",".join(record.retrieval_sources) or "unknown"
    warnings = ",".join(record.warnings) or "none"
    top_components = sorted(
        record.score_components.items(),
        key=lambda item: abs(item[1]),
        reverse=True,
    )[:5]
    components = ", ".join(f"{key}={value:+.3f}" for key, value in top_components)

    return "\n".join([
        f"PMC{record.pmc_id} | PMID {record.pmid or 'unknown'} | score {record.score:.3f}",
        f"  year: {record.year or 'unknown'} | sources: {sources} | warnings: {warnings}",
        f"  title: {record.title or '[missing title]'}",
        f"  top components: {components or 'none'}",
    ])

def print_summary(summary):
    print(f"Count: {summary['total']}")
    print("Retrieval sources:")
    for source, count in sorted(summary["retrieval_sources"].items()):
        print(f"  {source}: {count}")

    score = summary["score"]
    print("Score distribution:")
    print(f"  min/max: {score['min']:.3f}/{score['max']:.3f}")
    print(f"  mean/median: {score['mean']:.3f}/{score['median']:.3f}")
    print(f"  >=0.75: {score['above_0_75']}")
    print(f"  >=0.50: {score['above_0_50']}")
    print(f"  >=0.25: {score['above_0_25']}")
    print(f"  <0.10: {score['below_0_10']}")

    if summary["warnings"]:
        print("Warnings:")
        for warning, count in sorted(summary["warnings"].items()):
            print(f"  {warning}: {count}")

def _resolve_target_from_args(args, parser):
    locus = args.locus or args.gene
    if args.profile and args.organism:
        parser.error("use either --profile or --organism, not both")
    profile = args.profile
    if profile is None and args.organism is None:
        profile = "mtb-h37rv"
    try:
        target = targets.resolve_annotation_target(
            profile_identifier=profile,
            organism_identifier=args.organism,
            strain_identifier=args.strain,
            locus=locus,
            name=args.name,
            gene_name_cache_dir=args.gene_name_cache,
            allow_online_name_lookup=not args.no_online_name_lookup,
        )
    except ValueError as exc:
        parser.error(str(exc))

    gene_name_source = target.gene_name_source
    gene_name_source_detail = target.gene_name_source_detail
    gene_name_confidence = target.gene_name_confidence
    gene_name_aliases = target.gene_name_aliases
    gene_name_candidates = target.gene_name_candidates
    gene_name_warnings = target.gene_name_warnings
    resolved_name = target.resolved_name

    if target.submitted_name is not None:
        gene_name_source = gene_name_source or "supplied"
        gene_name_source_detail = gene_name_source_detail or "supplied argument"
        gene_name_confidence = gene_name_confidence or "curator_supplied"
        if args.cache_supplied_name and target.resolved_locus is not None and resolved_name:
            gene_names.cache_supplied_gene_name(
                target.profile,
                target.resolved_locus,
                resolved_name,
                cache_dir=args.gene_name_cache,
            )
    elif args.refresh_gene_name_cache and target.resolved_locus is not None:
        lookup_result = gene_names.resolve_gene_name(
            target.profile,
            target.resolved_locus,
            cache_dir=args.gene_name_cache,
            allow_online_lookup=not args.no_online_name_lookup,
            refresh_cache=True,
        )
        resolved_name = lookup_result.gene_name
        gene_name_source = lookup_result.source
        gene_name_source_detail = lookup_result.source_detail
        gene_name_confidence = lookup_result.confidence
        gene_name_aliases = list(lookup_result.aliases)
        gene_name_candidates = list(lookup_result.candidates)
        gene_name_warnings = list(lookup_result.warnings)

    return {
        "target": target,
        "gene": target.resolved_locus,
        "name": resolved_name,
        "gene_name_source": gene_name_source,
        "gene_name_source_detail": gene_name_source_detail,
        "gene_name_confidence": gene_name_confidence,
        "gene_name_aliases": gene_name_aliases,
        "gene_name_candidates": gene_name_candidates,
        "gene_name_warnings": gene_name_warnings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fetch and rank PMC papers for a gene target"
    )
    parser.add_argument("gene", nargs="?", help="Legacy gene locus shorthand (e.g. Rv0001)")
    parser.add_argument("--profile", help="Configured organism profile, e.g. mtb-h37rv")
    parser.add_argument("--organism", help="Organism/species name or synonym")
    parser.add_argument("--strain", help="Optional strain/isolate/reference name or synonym")
    parser.add_argument("--locus", help="Gene locus to fetch papers for")
    parser.add_argument("--name", help="Optional gene name/symbol for name-based retrieval")
    parser.add_argument("--cache", default="./.cache")
    parser.add_argument(
        "--gene-name-cache",
        default=gene_names.DEFAULT_GENE_NAME_CACHE_DIR,
        help="Directory for cached locus-to-gene-name records",
    )
    parser.add_argument(
        "--no-online-name-lookup",
        action="store_true",
        help="Disable NCBI/UniProt gene-name lookup before paper retrieval",
    )
    parser.add_argument(
        "--refresh-gene-name-cache",
        action="store_true",
        help="Ignore cached online gene-name records and refresh from online sources",
    )
    parser.add_argument(
        "--cache-supplied-name",
        action="store_true",
        help="Write --name into the gene-name cache as a manual curated record",
    )
    parser.add_argument("--top", type=int, default=10, help="Number of top ranked papers to print")
    parser.add_argument("--bottom", type=int, default=5, help="Number of bottom ranked papers to print")
    parser.add_argument("--target-relevance", type=float, default=DEFAULT_TARGET_RELEVANCE)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--min-papers", type=int, default=DEFAULT_MIN_PAPERS)
    parser.add_argument("--max-papers", type=int, default=DEFAULT_MAX_PAPERS)
    parser.add_argument("--max-rank", type=int, default=DEFAULT_MAX_RANK)
    parser.add_argument("--json-out", help="Optional path for full ranked relevance JSON")

    args = parser.parse_args(argv)
    context = _resolve_target_from_args(args, parser)
    target = context["target"]
    gene = context["gene"]
    name = context["name"]

    manager = PmcPaperManager(args.cache, organism_profile=target.profile)
    ranked_records = manager.get_ranked_papers(gene, name)
    summary = summarize_ranked_records(ranked_records)
    selection = manager.select_relevance_records(
        ranked_records,
        target_relevance=args.target_relevance,
        min_score=args.min_score,
        max_rank=args.max_rank,
        min_papers=args.min_papers,
        max_papers=args.max_papers,
    )
    selected = selection.selected_records
    cumulative = selection.cumulative_relevance

    print(f"\n\nProfile: {target.profile.profile_id}")
    print(f"Organism: {target.profile.canonical_name}")
    print(f"Gene: {gene}")
    print(f"Name: {name}")
    print(f"Name source: {context['gene_name_source']}")
    if context["gene_name_source_detail"]:
        print(f"Name source detail: {context['gene_name_source_detail']}")
    if context["gene_name_candidates"]:
        print("Name candidates:", ", ".join(context["gene_name_candidates"]))
    print_summary(summary)

    print(f"\nTop {args.top} PMC papers by relevance:")
    for record in ranked_records[:args.top]:
        print(format_record(record))

    print(f"\nBottom {args.bottom} PMC papers by relevance:")
    for record in ranked_records[-args.bottom:]:
        print(format_record(record))

    print("\nCumulative relevance simulation:")
    print(f"  selection mode: {selection.selection_mode}")
    print(f"  eligible papers: {selection.eligible_count}")
    print(f"  target relevance: {args.target_relevance:.3f}")
    print(f"  min papers: {args.min_papers}")
    print(f"  max papers: {args.max_papers}")
    print(f"  min score: {args.min_score:.3f}")
    print(f"  max rank: {args.max_rank}")
    print(f"  selected papers: {len(selected)}")
    print(f"  cumulative relevance: {cumulative:.3f}")
    print("  selected PMC IDs:", ", ".join(f"PMC{record.pmc_id}" for record in selected))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf8") as output_file:
            # JSON output keeps full per-paper evidence so ranking changes can
            # be compared across runs or reviewed without scraping console text.
            json.dump(
                {
                    "gene": gene,
                    "name": name,
                    "gene_name_source": context["gene_name_source"],
                    "gene_name_source_detail": context["gene_name_source_detail"],
                    "gene_name_candidates": context["gene_name_candidates"],
                    "gene_name_confidence": context["gene_name_confidence"],
                    "gene_name_aliases": context["gene_name_aliases"],
                    "gene_name_warnings": context["gene_name_warnings"],
                    **target.to_preflight_dict(),
                    "summary": summary,
                    "ranked_records": [
                        relevance_record_to_dict(record)
                        for record in ranked_records
                    ],
                },
                output_file,
                indent=2,
            )
        print(f"\nWrote ranked relevance data to {args.json_out}")

    return {
        "gene": gene,
        "name": name,
        "primary_identifier": target.primary_identifier,
        "gene_name_source": context["gene_name_source"],
        "gene_name_source_detail": context["gene_name_source_detail"],
        "gene_name_candidates": context["gene_name_candidates"],
        "profile_id": target.profile.profile_id,
        "canonical_name": target.profile.canonical_name,
        "species_name": target.profile.species_name,
        "strain": target.profile.strain,
        "summary": summary,
        "ranked_records": ranked_records,
        "selection": selection,
    }

if __name__ == "__main__":
    main()