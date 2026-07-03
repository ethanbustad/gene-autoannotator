import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import quote

from . import gene_names
from . import http_
from . import organisms

log = logging.getLogger(__name__)

KEGG_SSDB_BEST_URL = 'https://www.kegg.jp/ssdb-bin/ssdb_best?org_gene={org_gene}'
MIN_ORTHOLOG_IDENTITY = 0.30
SSDB_ENTRY_PATTERN = re.compile(
    r'<A HREF="/entry/([a-z]{3,4}:[^"]+)"[^>]*>\1</A>\s+([^<]*?)\s*'
    r'<A HREF="/entry/K\d+"[^>]*>K\d+</a>\s+(\d+)\s+(\d+)\s+([\d.]+)\s+(\d+)',
    re.IGNORECASE | re.DOTALL,
)

KEGG_ORGANISM_NAMES = {
    'mtu': 'Mycobacterium tuberculosis',
    'msm': 'Mycobacterium smegmatis',
    'mory': 'Mycobacterium orygis',
    'mmar': 'Mycobacterium marinum',
    'tcr': 'Trypanosoma cruzi',
    'eco': 'Escherichia coli',
}

# Minimal retrieval/scoring hints for ortholog-source organisms that lack a
# built-in profile. Used only for ortholog paper passes.
KEGG_ORGANISM_PROFILE_HINTS = {
    'msm': {
        'profile_id': 'kegg-msm',
        'canonical_name': 'Mycobacterium smegmatis',
        'species_name': 'Mycobacterium smegmatis',
        'strain': None,
        'synonyms': ('msm',),
        'species_synonyms': ('m smegmatis', 'm. smegmatis'),
        'strain_synonyms': (),
        'locus_regex': r'^MSMEG_\d+$',
        'search_terms': ('Mycobacterium smegmatis', 'M. smegmatis', 'M. smeg'),
        'target_patterns': (
            r'Mycobacterium\ssmegmatis',
            r'M.\ssmegmatis',
            r'M.\ssmeg',
        ),
        'off_target_patterns': (
            r'\bEscherichia\s+coli\b',
            r'\bE\.?\s*coli\b',
        ),
        'excluded_species_patterns': (),
    },
    'mory': {
        'profile_id': 'kegg-mory',
        'canonical_name': 'Mycobacterium orygis',
        'species_name': 'Mycobacterium orygis',
        'strain': None,
        'synonyms': ('mory',),
        'species_synonyms': ('m orygis', 'm. orygis'),
        'strain_synonyms': (),
        'locus_regex': r'^MO_\d+$',
        'search_terms': ('Mycobacterium orygis', 'M. orygis'),
        'target_patterns': (
            r'Mycobacterium\sorygis',
            r'M.\sorygis',
        ),
        'off_target_patterns': (
            r'\bEscherichia\s+coli\b',
            r'\bE\.?\s*coli\b',
        ),
        'excluded_species_patterns': (),
    },
    'mmar': {
        'profile_id': 'kegg-mmar',
        'canonical_name': 'Mycobacterium marinum',
        'species_name': 'Mycobacterium marinum',
        'strain': None,
        'synonyms': ('mmar',),
        'species_synonyms': ('m marinum', 'm. marinum'),
        'strain_synonyms': (),
        'locus_regex': r'^MMAR_\d+$',
        'search_terms': ('Mycobacterium marinum', 'M. marinum'),
        'target_patterns': (
            r'Mycobacterium\smarinum',
            r'M.\smarinum',
        ),
        'off_target_patterns': (
            r'\bEscherichia\s+coli\b',
            r'\bE\.?\s*coli\b',
        ),
        'excluded_species_patterns': (),
    },
    'tcr': {
        'profile_id': 'kegg-tcr',
        'canonical_name': 'Trypanosoma cruzi',
        'species_name': 'Trypanosoma cruzi',
        'strain': None,
        'synonyms': ('tcr',),
        'species_synonyms': ('t cruzi', 't. cruzi'),
        'strain_synonyms': (),
        'locus_regex': r'^TcCLB\.\d+\.\d+$',
        'search_terms': ('Trypanosoma cruzi', 'T. cruzi'),
        'target_patterns': (
            r'Trypanosoma\scruzi',
            r'T.\scruzi',
        ),
        'off_target_patterns': (
            r'\bEscherichia\s+coli\b',
            r'\bE\.?\s*coli\b',
            r'Trypanosoma\sbrucei',
            r'T.\sbrucei',
        ),
        'excluded_species_patterns': (),
    },
}


@dataclass(frozen=True)
class OrthologHit:
    source_organism_code: str
    source_organism_name: str | None
    source_gene_id: str
    source_gene_name: str | None
    score: float | None
    lookup_source: str
    identity: float | None = None
    raw_response: str | None = None

    def to_metadata(self):
        return {
            'source_organism_code': self.source_organism_code,
            'source_organism_name': self.source_organism_name,
            'source_gene_id': self.source_gene_id,
            'source_gene_name': self.source_gene_name,
            'score': self.score,
            'identity': self.identity,
            'lookup_source': self.lookup_source,
        }


@dataclass
class OrthologPassResult:
    ran: bool
    skipped_reason: str | None
    ortholog_annotation: dict | None
    papers_analyzed: list[str]
    pmids_analyzed: list[str]
    fields_filled: list[str]
    fields_requested: list[str] | None = None


def parse_ssdb_hits(html, query_organism_code):
    """Parse KEGG SSDB best-hit HTML into all non-self hits, best score first."""
    query_code = query_organism_code.lower()
    hits = []
    for match in SSDB_ENTRY_PATTERN.finditer(html):
        org_gene, description, _length, sw_score, identity, _overlap = match.groups()
        org_code, gene_id = org_gene.split(':', 1)
        if org_code.lower() == query_code:
            continue
        description = ' '.join(description.split())
        hits.append(OrthologHit(
            source_organism_code=org_code.lower(),
            source_organism_name=KEGG_ORGANISM_NAMES.get(org_code.lower()),
            source_gene_id=gene_id,
            source_gene_name=description or None,
            score=float(sw_score),
            identity=float(identity),
            lookup_source='kegg_ssdb',
            raw_response=None,
        ))
    return hits


def parse_ssdb_best_response(html, query_organism_code):
    """Backward-compatible: return the first non-self hit (table order)."""
    hits = parse_ssdb_hits(html, query_organism_code)
    return hits[0] if hits else None


def _cache_path(cache_dir, kegg_organism_code, gene_locus):
    key = f'{kegg_organism_code}:{gene_locus}'.lower()
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]
    return os.path.join(cache_dir, 'orthologs', f'{digest}.json')


def lookup_top_ortholog(kegg_organism_code, gene_locus, cache_dir='./.cache', *, fetch_html=None):
    if not kegg_organism_code or not gene_locus:
        return None

    cache_file = _cache_path(cache_dir, kegg_organism_code, gene_locus)
    if os.path.isfile(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as handle:
                cached = json.load(handle)
            if cached is None:
                return None
            hit = OrthologHit(**{**cached, 'raw_response': None})
            log.debug(
                'Using cached ortholog hit %s:%s for %s:%s',
                hit.source_organism_code,
                hit.source_gene_id,
                kegg_organism_code,
                gene_locus,
            )
            return hit
        except (json.JSONDecodeError, TypeError, KeyError):
            log.warning('Invalid ortholog cache at %s; refetching', cache_file)

    org_gene = f'{kegg_organism_code}:{gene_locus}'
    url = KEGG_SSDB_BEST_URL.format(org_gene=quote(org_gene, safe=':'))
    try:
        if fetch_html is not None:
            html = fetch_html(url)
        else:
            throttler = http_.Throttler()
            response = throttler.get(url, 'kegg.jp')
            html = response.text
    except Exception as exc:
        log.warning('KEGG SSDB lookup failed for %s: %s', org_gene, exc)
        return None

    hit = parse_ssdb_best_response(html, kegg_organism_code)
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'w', encoding='utf-8') as handle:
        if hit is None:
            json.dump(None, handle)
        else:
            json.dump(hit.to_metadata(), handle, indent=2)
    return hit


def profile_for_kegg_organism(kegg_code):
    kegg_code = kegg_code.lower()
    for profile in organisms.PROFILES:
        if profile.kegg_organism_code and profile.kegg_organism_code.lower() == kegg_code:
            return profile
    hints = KEGG_ORGANISM_PROFILE_HINTS.get(kegg_code)
    if hints is None:
        organism_name = KEGG_ORGANISM_NAMES.get(kegg_code, kegg_code)
        hints = {
            'profile_id': f'kegg-{kegg_code}',
            'canonical_name': organism_name,
            'species_name': organism_name,
            'strain': None,
            'synonyms': (kegg_code,),
            'species_synonyms': (),
            'strain_synonyms': (),
            'locus_regex': r'^.+$',
            'search_terms': (organism_name,),
            'target_patterns': (re.escape(organism_name),),
            'off_target_patterns': (
                r'\bEscherichia\s+coli\b',
                r'\bE\.?\s*coli\b',
            ),
            'excluded_species_patterns': (),
        }
    return organisms.OrganismProfile(
        profile_id=hints['profile_id'],
        canonical_name=hints['canonical_name'],
        species_name=hints['species_name'],
        strain=hints.get('strain'),
        synonyms=tuple(hints.get('synonyms') or ()),
        species_synonyms=tuple(hints.get('species_synonyms') or ()),
        strain_synonyms=tuple(hints.get('strain_synonyms') or ()),
        locus_regex=hints.get('locus_regex') or r'^.+$',
        search_terms=tuple(hints.get('search_terms') or ()),
        target_patterns=tuple(hints.get('target_patterns') or ()),
        off_target_patterns=tuple(hints.get('off_target_patterns') or ()),
        excluded_species_patterns=tuple(hints.get('excluded_species_patterns') or ()),
        kegg_organism_code=kegg_code,
    )


def supports_ortholog_literature_pass(hit):
    """Whether the ortholog organism has enough profile metadata for a paper pass."""
    if hit is None:
        return False
    code = hit.source_organism_code.lower()
    if code in KEGG_ORGANISM_PROFILE_HINTS:
        return True
    for profile in organisms.PROFILES:
        if profile.kegg_organism_code and profile.kegg_organism_code.lower() == code:
            return True
    return False


def select_best_profiled_ortholog(hits, *, min_identity=MIN_ORTHOLOG_IDENTITY):
    """Pick the highest-SW-score hit that has a saved profile/hint and clears the
    identity floor. Returns None when no hit qualifies."""
    qualifying = [
        hit for hit in hits
        if supports_ortholog_literature_pass(hit)
        and hit.identity is not None
        and hit.identity >= min_identity
    ]
    if not qualifying:
        return None
    return max(qualifying, key=lambda hit: (hit.score if hit.score is not None else 0.0))


_GENE_SYMBOL_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,11}$')


def _is_descriptive_kegg_name(name):
    if not name:
        return False
    if ' ' in name or ',' in name:
        return True
    return len(name) > 20


def _looks_like_gene_symbol(name):
    if not name or not isinstance(name, str):
        return False
    return bool(_GENE_SYMBOL_PATTERN.fullmatch(name.strip()))


def resolve_ortholog_gene_name(
    hit,
    cache_dir,
    *,
    allow_online_lookup=False,
    target_gene_name=None,
):
    profile = profile_for_kegg_organism(hit.source_organism_code)
    if profile.annotation_table_path:
        lookup = gene_names.resolve_gene_name(
            profile,
            hit.source_gene_id,
            cache_dir=cache_dir,
            allow_online_lookup=allow_online_lookup,
        )
        if lookup.gene_name and lookup.gene_name != hit.source_gene_id:
            if not _is_descriptive_kegg_name(lookup.gene_name):
                return lookup.gene_name

    kegg_name = hit.source_gene_name
    if kegg_name and kegg_name != hit.source_gene_id and not _is_descriptive_kegg_name(kegg_name):
        return kegg_name

    if _looks_like_gene_symbol(target_gene_name):
        return target_gene_name.strip()

    return hit.source_gene_id
