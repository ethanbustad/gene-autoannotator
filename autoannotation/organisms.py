import re
from dataclasses import asdict, dataclass


class UnknownOrganismError(ValueError):
    """Raised when an organism identifier does not resolve to a configured profile."""


class DuplicateOrganismSynonymError(ValueError):
    """Raised when two profiles claim the same normalized organism synonym."""


@dataclass(frozen=True)
class OrganismProfile:
    profile_id: str
    canonical_name: str
    species_name: str
    strain: str | None
    synonyms: tuple[str, ...]
    species_synonyms: tuple[str, ...]
    strain_synonyms: tuple[str, ...]
    locus_regex: str
    search_terms: tuple[str, ...]


@dataclass(frozen=True)
class LocusValidationResult:
    valid: bool
    profile_id: str | None
    canonical_name: str | None
    species_name: str | None
    strain: str | None
    supplied_organism: str
    supplied_locus: str
    normalized_locus: str
    matched_organism_synonym: str | None
    matched_locus_schema: bool
    reason: str | None = None

    def to_dict(self):
        return asdict(self)


PROFILES = (
    OrganismProfile(
        profile_id="mtb-h37rv",
        canonical_name="Mycobacterium tuberculosis H37Rv",
        species_name="Mycobacterium tuberculosis",
        strain="H37Rv",
        synonyms=(
            "mtb-h37rv",
            "mtb h37rv",
            "m tuberculosis h37rv",
            "m. tuberculosis h37rv",
            "mycobacterium tuberculosis h37rv",
            "mycobacteriumtuberculosish37rv",
        ),
        species_synonyms=(
            "mtb",
            "m tuberculosis",
            "m. tuberculosis",
            "mycobacterium tuberculosis",
        ),
        strain_synonyms=(
            "h37rv",
            "h37 rv",
        ),
        locus_regex=r"^Rv\d{4}[Ac]?$",
        search_terms=(
            "Mycobacterium tuberculosis",
            "M. tuberculosis",
            "Mtb",
            "H37Rv",
        ),
    ),
    OrganismProfile(
        profile_id="morygis-51145",
        canonical_name="Mycobacterium orygis 51145",
        species_name="Mycobacterium orygis",
        strain="51145",
        synonyms=(
            "morygis-51145",
            "m orygis 51145",
            "m. orygis 51145",
            "mycobacterium orygis 51145",
            "mycobacteriumorygis51145",
        ),
        species_synonyms=(
            "m orygis",
            "m. orygis",
            "mycobacterium orygis",
        ),
        strain_synonyms=("51145",),
        locus_regex=r"^RJtmp_\d{6}$",
        search_terms=(
            "Mycobacterium orygis",
            "M. orygis",
            "51145",
        ),
    ),
    OrganismProfile(
        profile_id="mmarinum-m",
        canonical_name="Mycobacterium marinum M",
        species_name="Mycobacterium marinum",
        strain="M",
        synonyms=(
            "mmarinum-m",
            "m marinum m",
            "m. marinum m",
            "mycobacterium marinum m",
            "mycobacteriummarinumm",
        ),
        species_synonyms=(
            "m marinum",
            "m. marinum",
            "mycobacterium marinum",
        ),
        strain_synonyms=("m",),
        locus_regex=r"^MMAR_\d{4}$",
        search_terms=(
            "Mycobacterium marinum",
            "M. marinum",
        ),
    ),
    OrganismProfile(
        profile_id="tcruzi-clbrener",
        canonical_name="Trypanosoma cruzi CL Brener",
        species_name="Trypanosoma cruzi",
        strain="CL Brener",
        synonyms=(
            "tcruzi-clbrener",
            "t cruzi cl brener",
            "t. cruzi cl brener",
            "trypanosoma cruzi cl brener",
            "trypanosomacruziclbrener",
        ),
        species_synonyms=(
            "t cruzi",
            "t. cruzi",
            "trypanosoma cruzi",
        ),
        strain_synonyms=(
            "cl brener",
            "clbrener",
        ),
        locus_regex=r"^TcCLB\.\d+\.\d+$",
        search_terms=(
            "Trypanosoma cruzi",
            "T. cruzi",
            "CL Brener",
        ),
    ),
    OrganismProfile(
        profile_id="tcruzi-dm28c",
        canonical_name="Trypanosoma cruzi Dm28c",
        species_name="Trypanosoma cruzi",
        strain="Dm28c",
        synonyms=(
            "tcruzi-dm28c",
            "t cruzi dm28c",
            "t. cruzi dm28c",
            "trypanosoma cruzi dm28c",
            "trypanosomacruzidm28c",
        ),
        species_synonyms=(
            "t cruzi",
            "t. cruzi",
            "trypanosoma cruzi",
        ),
        strain_synonyms=("dm28c",),
        locus_regex=r"^TCDM_\d{5}$",
        search_terms=(
            "Trypanosoma cruzi",
            "T. cruzi",
            "Dm28c",
        ),
    ),
)


def normalize_identifier(identifier):
    return re.sub(r"[^a-z0-9]+", "", identifier.casefold())


def _build_synonym_index(profiles=PROFILES):
    index = {}
    for profile in profiles:
        identifiers = (profile.profile_id, profile.canonical_name, *profile.synonyms)
        for synonym in identifiers:
            normalized = normalize_identifier(synonym)
            existing = index.get(normalized)
            if existing is not None and existing.profile_id != profile.profile_id:
                raise DuplicateOrganismSynonymError(
                    f'Organism synonym "{synonym}" is shared by '
                    f"{existing.profile_id} and {profile.profile_id}"
                )
            index[normalized] = profile
    return index


def _build_species_index(profiles=PROFILES):
    index = {}
    for profile in profiles:
        identifiers = (profile.species_name, *profile.species_synonyms)
        for synonym in identifiers:
            normalized = normalize_identifier(synonym)
            index.setdefault(normalized, [])
            if profile not in index[normalized]:
                index[normalized].append(profile)
    return index


_PROFILE_BY_SYNONYM = _build_synonym_index()
_PROFILES_BY_SPECIES_SYNONYM = _build_species_index()


def resolve_profile(identifier):
    normalized = normalize_identifier(identifier)
    try:
        return _PROFILE_BY_SYNONYM[normalized]
    except KeyError as exc:
        raise UnknownOrganismError(f"Unknown organism profile: {identifier}") from exc


def resolve_species_profiles(identifier):
    normalized = normalize_identifier(identifier)
    try:
        return tuple(_PROFILES_BY_SPECIES_SYNONYM[normalized])
    except KeyError as exc:
        raise UnknownOrganismError(f"Unknown organism species: {identifier}") from exc


def _matches_strain(profile, strain_identifier):
    if profile.strain is None:
        return strain_identifier is None
    normalized = normalize_identifier(strain_identifier)
    identifiers = (profile.strain, *profile.strain_synonyms)
    return normalized in {normalize_identifier(identifier) for identifier in identifiers}


def validate_locus(profile, locus):
    return re.fullmatch(profile.locus_regex, locus) is not None


def _result_for_profile(profile, organism_identifier, locus, *, valid, reason=None):
    return LocusValidationResult(
        valid=valid,
        profile_id=profile.profile_id,
        canonical_name=profile.canonical_name,
        species_name=profile.species_name,
        strain=profile.strain,
        supplied_organism=organism_identifier,
        supplied_locus=locus,
        normalized_locus=locus,
        matched_organism_synonym=organism_identifier,
        matched_locus_schema=valid,
        reason=reason,
    )


def _invalid_result(organism_identifier, locus, reason):
    return LocusValidationResult(
        valid=False,
        profile_id=None,
        canonical_name=None,
        species_name=None,
        strain=None,
        supplied_organism=organism_identifier,
        supplied_locus=locus,
        normalized_locus=locus,
        matched_organism_synonym=None,
        matched_locus_schema=False,
        reason=reason,
    )


def validate_locus_request(
    *,
    locus,
    profile_identifier=None,
    organism_identifier=None,
    strain_identifier=None,
):
    if profile_identifier is not None:
        try:
            profile = resolve_profile(profile_identifier)
        except UnknownOrganismError:
            return _invalid_result(profile_identifier, locus, "unknown_profile")
        matched_locus_schema = validate_locus(profile, locus)
        return _result_for_profile(
            profile,
            profile_identifier,
            locus,
            valid=matched_locus_schema,
            reason=None if matched_locus_schema else "locus_schema_mismatch",
        )

    if organism_identifier is None:
        raise ValueError("organism_identifier or profile_identifier is required")

    try:
        candidate_profiles = resolve_species_profiles(organism_identifier)
    except UnknownOrganismError:
        return _invalid_result(organism_identifier, locus, "unknown_organism")

    if strain_identifier is not None:
        candidate_profiles = tuple(
            profile for profile in candidate_profiles
            if _matches_strain(profile, strain_identifier)
        )
        if not candidate_profiles:
            return _invalid_result(organism_identifier, locus, "unknown_strain")

    matching_profiles = [
        profile for profile in candidate_profiles
        if validate_locus(profile, locus)
    ]
    if len(matching_profiles) == 1:
        return _result_for_profile(matching_profiles[0], organism_identifier, locus, valid=True)
    if len(matching_profiles) > 1:
        return _invalid_result(organism_identifier, locus, "ambiguous_profile")
    return _invalid_result(organism_identifier, locus, "locus_schema_mismatch")


def validate_organism_locus(organism_identifier, locus):
    try:
        resolve_profile(organism_identifier)
    except UnknownOrganismError:
        return validate_locus_request(
            organism_identifier=organism_identifier,
            locus=locus,
        )
    return validate_locus_request(
        profile_identifier=organism_identifier,
        locus=locus,
    )
