import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import quote_plus

import pandas as pd
import requests

log = logging.getLogger(__name__)

DEFAULT_GENE_NAME_CACHE_DIR = os.path.join('.cache', 'gene_names')
NCBI_BASE_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
UNIPROT_SEARCH_URL = 'https://rest.uniprot.org/uniprotkb/search'

GENE_NAME_SOURCES = frozenset({
    'supplied',
    'annotation_table',
    'cache',
    'ncbi_gene',
    'uniprot',
    'manual_cache',
    'locus_fallback',
})


@dataclass(frozen=True)
class GeneNameRecord:
    profile_id: str
    locus: str
    gene_name: str
    source: str
    source_detail: str | None = None
    confidence: str = 'clear'
    aliases: list[str] = field(default_factory=list)
    looked_up_at: str | None = None

    def to_dict(self):
        payload = asdict(self)
        if payload['looked_up_at'] is None:
            payload['looked_up_at'] = datetime.now(timezone.utc).isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload):
        return cls(
            profile_id=payload['profile_id'],
            locus=payload['locus'],
            gene_name=payload['gene_name'],
            source=payload['source'],
            source_detail=payload.get('source_detail'),
            confidence=payload.get('confidence', 'clear'),
            aliases=list(payload.get('aliases') or []),
            looked_up_at=payload.get('looked_up_at'),
        )


@dataclass(frozen=True)
class GeneNameLookupResult:
    gene_name: str | None
    source: str
    source_detail: str | None = None
    confidence: str = 'clear'
    aliases: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_record(self, profile, locus):
        if not self.gene_name:
            return None
        return GeneNameRecord(
            profile_id=profile.profile_id,
            locus=locus,
            gene_name=self.gene_name,
            source=self.source,
            source_detail=self.source_detail,
            confidence=self.confidence,
            aliases=list(self.aliases),
            looked_up_at=datetime.now(timezone.utc).isoformat(),
        )


class GeneNameSource(Protocol):
    def lookup(self, profile, locus) -> GeneNameLookupResult | None:
        ...


def _cache_path(cache_dir, profile_id):
    return os.path.join(str(cache_dir), f'{profile_id}.json')


def _read_cache(cache_dir, profile_id):
    path = _cache_path(cache_dir, profile_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf8') as cache_file:
            payload = json.load(cache_file)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        log.warning('Ignoring unreadable gene-name cache file: %s', path)
        return {}


def lookup_cached_gene_name(profile, locus, cache_dir=DEFAULT_GENE_NAME_CACHE_DIR):
    payload = _read_cache(cache_dir, profile.profile_id)
    record_payload = payload.get(locus)
    if not isinstance(record_payload, dict):
        return None
    try:
        record = GeneNameRecord.from_dict(record_payload)
    except (KeyError, TypeError):
        return None
    source = 'manual_cache' if record.source == 'manual_cache' else 'cache'
    source_detail = record.source_detail
    if source == 'cache' and record.source:
        source_detail = f'Cached {record.source}: {source_detail or "no source detail"}'
    return GeneNameLookupResult(
        gene_name=record.gene_name,
        source=source,
        source_detail=source_detail,
        confidence=record.confidence,
        aliases=list(record.aliases),
    )


def write_cached_gene_name(record, cache_dir=DEFAULT_GENE_NAME_CACHE_DIR):
    os.makedirs(cache_dir, exist_ok=True)
    payload = _read_cache(cache_dir, record.profile_id)
    payload[record.locus] = record.to_dict()
    with open(_cache_path(cache_dir, record.profile_id), 'w', encoding='utf8') as cache_file:
        json.dump(payload, cache_file, indent=2, sort_keys=True)


def _aliases_for_supplied_name(gene_name):
    aliases = []
    if gene_name.casefold().startswith('tc') and len(gene_name) > 2:
        aliases.append(gene_name[2:])
    return aliases


def cache_supplied_gene_name(
    profile,
    locus,
    gene_name,
    cache_dir=DEFAULT_GENE_NAME_CACHE_DIR,
):
    record = GeneNameRecord(
        profile_id=profile.profile_id,
        locus=locus,
        gene_name=gene_name,
        source='manual_cache',
        source_detail='Cached from user-supplied --name',
        confidence='curator_supplied',
        aliases=_aliases_for_supplied_name(gene_name),
        looked_up_at=datetime.now(timezone.utc).isoformat(),
    )
    write_cached_gene_name(record, cache_dir)
    return record


def lookup_annotation_table_gene_name(profile, locus):
    if not profile.annotation_table_path:
        return None
    try:
        table = pd.read_csv(profile.annotation_table_path, sep='\t')
    except FileNotFoundError:
        return None

    if profile.annotation_feature_column and profile.annotation_feature_value:
        table = table.loc[
            table[profile.annotation_feature_column].eq(profile.annotation_feature_value),
            :,
        ]
    table = table.set_index(profile.annotation_id_column, drop=True)
    if locus not in table.index:
        return None
    gene_name = table.at[locus, profile.annotation_name_column]
    if not gene_name:
        return None
    return GeneNameLookupResult(
        gene_name=gene_name,
        source='annotation_table',
        source_detail=profile.annotation_table_path,
        confidence='profile_table',
    )


class NcbiGeneSource:
    def __init__(self, session=None, timeout=20):
        self.session = session or requests
        self.timeout = timeout

    def lookup(self, profile, locus):
        term = (
            f'{quote_plus(locus)}[All+Fields]+AND+'
            f'{quote_plus(profile.species_name)}[Organism]'
        )
        search_url = (
            f'{NCBI_BASE_URL}esearch.fcgi?db=gene&retmode=json&retmax=5&term={term}'
        )
        try:
            search_response = self.session.get(search_url, timeout=self.timeout)
            search_response.raise_for_status()
            search_result = search_response.json()
        except (requests.RequestException, ValueError) as exc:
            return GeneNameLookupResult(
                gene_name=None,
                source='ncbi_gene',
                source_detail=search_url,
                warnings=[f'ncbi_lookup_failed:{exc.__class__.__name__}'],
            )
        ids = search_result.get('esearchresult', {}).get('idlist', [])
        if len(ids) != 1:
            return GeneNameLookupResult(
                gene_name=None,
                source='ncbi_gene',
                source_detail=search_url,
                candidates=list(ids),
                warnings=['ambiguous_gene_name' if ids else 'no_gene_name_found'],
            )

        summary_url = (
            f'{NCBI_BASE_URL}esummary.fcgi?db=gene&retmode=json&id={ids[0]}'
        )
        try:
            summary_response = self.session.get(summary_url, timeout=self.timeout)
            summary_response.raise_for_status()
            summary = summary_response.json()
        except (requests.RequestException, ValueError) as exc:
            return GeneNameLookupResult(
                gene_name=None,
                source='ncbi_gene',
                source_detail=summary_url,
                warnings=[f'ncbi_lookup_failed:{exc.__class__.__name__}'],
            )
        record = summary.get('result', {}).get(ids[0], {})
        gene_name = record.get('name') or record.get('description')
        if not gene_name:
            return None
        aliases = [
            item.strip()
            for item in str(record.get('otheraliases') or '').split(',')
            if item.strip()
        ]
        return GeneNameLookupResult(
            gene_name=gene_name,
            source='ncbi_gene',
            source_detail=summary_url,
            confidence='clear',
            aliases=aliases,
        )


class UniProtSource:
    def __init__(self, session=None, timeout=20):
        self.session = session or requests
        self.timeout = timeout

    def lookup(self, profile, locus):
        query = f'({locus}) AND (organism_name:"{profile.species_name}")'
        params = {
            'query': query,
            'format': 'json',
            'fields': 'gene_names,accession,protein_name,organism_name',
            'size': 5,
        }
        try:
            response = self.session.get(UNIPROT_SEARCH_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            return GeneNameLookupResult(
                gene_name=None,
                source='uniprot',
                source_detail=UNIPROT_SEARCH_URL,
                warnings=[f'uniprot_lookup_failed:{exc.__class__.__name__}'],
            )
        results = payload.get('results', [])
        candidates = []
        for result in results:
            genes = result.get('genes') or []
            for gene in genes:
                name = gene.get('geneName', {}).get('value')
                if name:
                    candidates.append(name)
        unique_candidates = sorted(set(candidates))
        if len(unique_candidates) == 1:
            return GeneNameLookupResult(
                gene_name=unique_candidates[0],
                source='uniprot',
                source_detail=UNIPROT_SEARCH_URL,
                confidence='clear',
                aliases=[candidate for candidate in unique_candidates[1:]],
            )
        return GeneNameLookupResult(
            gene_name=None,
            source='uniprot',
            source_detail=UNIPROT_SEARCH_URL,
            candidates=unique_candidates,
            warnings=['ambiguous_gene_name' if unique_candidates else 'no_gene_name_found'],
        )


def default_online_sources():
    return [NcbiGeneSource(), UniProtSource()]


def _fallback_result(locus, candidates=None, warnings=None):
    return GeneNameLookupResult(
        gene_name=locus,
        source='locus_fallback',
        source_detail='No reliable gene name found; using locus as name.',
        confidence='fallback',
        candidates=list(candidates or []),
        warnings=list(warnings or []),
    )


def resolve_gene_name(
    profile,
    locus,
    *,
    cache_dir=DEFAULT_GENE_NAME_CACHE_DIR,
    allow_online_lookup=True,
    refresh_cache=False,
    sources=None,
):
    table_result = lookup_annotation_table_gene_name(profile, locus)
    if table_result and table_result.gene_name:
        return table_result

    if not refresh_cache:
        cache_result = lookup_cached_gene_name(profile, locus, cache_dir)
        if cache_result and cache_result.gene_name:
            return cache_result

    if not allow_online_lookup:
        return _fallback_result(locus)

    candidates = []
    warnings = []
    for source in sources if sources is not None else default_online_sources():
        result = source.lookup(profile, locus)
        if result is None:
            continue
        candidates.extend(result.candidates)
        warnings.extend(result.warnings)
        if result.gene_name:
            record = result.to_record(profile, locus)
            if record is not None:
                write_cached_gene_name(record, cache_dir)
            return result

    return _fallback_result(locus, candidates=candidates, warnings=warnings)
