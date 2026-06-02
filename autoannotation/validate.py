import argparse
import json
import sys

from .organisms import validate_locus_request, validate_organism_locus


def main(argv=None):
    # Lightweight diagnostics CLI for profile/locus resolution. It mirrors the
    # validation path used by the API before jobs are queued.
    parser = argparse.ArgumentParser(
        description="Validate an organism profile identifier and gene locus."
    )
    parser.add_argument(
        "identifier",
        nargs="?",
        help="Configured profile/species identifier for shorthand use, e.g. mtb-h37rv",
    )
    parser.add_argument(
        "positional_locus",
        nargs="?",
        help="Gene locus for shorthand use.",
    )
    parser.add_argument("--profile", help="Configured organism profile, e.g. mtb-h37rv.")
    parser.add_argument("--organism", help="Organism/species name or synonym.")
    parser.add_argument("--strain", help="Optional strain/isolate/reference name or synonym.")
    parser.add_argument("--locus", help="Gene locus to validate.")
    args = parser.parse_args(argv)

    locus = args.locus or args.positional_locus
    if args.profile and args.organism:
        parser.error("use either --profile or --organism, not both")
    if (args.profile or args.organism) and args.identifier:
        parser.error("do not combine positional identifier with --profile or --organism")
    if locus is None:
        parser.error("a locus is required")

    if args.profile:
        result = validate_locus_request(profile_identifier=args.profile, locus=locus)
    elif args.organism:
        result = validate_locus_request(
            organism_identifier=args.organism,
            strain_identifier=args.strain,
            locus=locus,
        )
    elif args.identifier:
        result = validate_organism_locus(args.identifier, locus)
    else:
        parser.error("an organism/profile identifier is required")

    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.valid else 1


if __name__ == "__main__":
    sys.exit(main())
