import hashlib
import json
import logging
import os
import re

import ollama

from . import organisms
from . import utils

logging.basicConfig(format='%(asctime)s %(levelname).1s | %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

BIOLOGY_FIELDS = (
    'function',
    'functional_category',
    'drug_susc_impact',
    'infection_impact',
    'essential_in_vitro',
    'essential_in_vivo',
)

UNKNOWN_STRINGS = frozenset({
    '',
    'unknown',
    'missing',
    'n/a',
    'na',
    'not available',
    'insufficient',
    'insufficient evidence',
    'not stated',
    'not reported',
})

SECTION_HINTS = {
    'abstract': (
        'This excerpt is an abstract. Prioritize mechanism and functional category when '
        'explicitly stated. Do not infer essentiality or drug/infection impacts unless '
        'this text clearly reports them.'
    ),
    'results': (
        'This excerpt is from results. Prioritize experimental essentiality, drug '
        'susceptibility phenotypes, and measured infection phenotypes when explicitly '
        'reported.'
    ),
    'discussion': (
        'This excerpt is from discussion. Prioritize infection impact and mechanistic '
        'interpretation when explicitly stated; do not treat speculation as established fact.'
    ),
}


def is_unknown_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in UNKNOWN_STRINGS
    if isinstance(value, list):
        return len(value) == 0
    return False


def normalize_annotation_fields(parsed, *, require_biology_keys=False, organism_profile=None):
    """Map empty or placeholder values to JSON null; keep gene identity fields as strings."""
    normalized = {
        'gene_id': parsed.get('gene_id') or parsed.get('rv_id'),
        'name': parsed.get('name'),
    }
    if 'rv_id' in parsed:
        normalized['rv_id'] = parsed.get('rv_id')
    elif (
        organism_profile is not None
        and organism_profile.profile_id == 'mtb-h37rv'
        and normalized['gene_id']
    ):
        normalized['rv_id'] = normalized['gene_id']
    for field in BIOLOGY_FIELDS:
        if field not in parsed and not require_biology_keys:
            continue
        value = parsed.get(field)
        if is_unknown_value(value):
            normalized[field] = None
        elif field == 'functional_category' and isinstance(value, list):
            categories = [item for item in value if item and str(item).strip()]
            normalized[field] = categories if categories else None
        else:
            normalized[field] = value
    if 'annotation_notes' in parsed:
        notes = parsed.get('annotation_notes')
        normalized['annotation_notes'] = None if is_unknown_value(notes) else notes
    return normalized


def _nullable_string(description):
    return {
        'type': ['string', 'null'],
        'description': description + ' Use null when the source text does not support this field.',
    }


def _nullable_bool(description):
    return {
        'type': ['boolean', 'null'],
        'description': (
            description
            + ' Use null when the source text does not report experimental evidence for this field.'
        ),
    }


def _biology_properties(organism_label='the organism'):
    return {
        'function': _nullable_string(
            'What the gene product does for the cell (one or two concise sentences).'
        ),
        'functional_category': {
            'type': ['array', 'null'],
            'items': {'type': 'string'},
            'description': (
                'One or more general cellular functions (e.g., cell wall, respiration, '
                'virulence, DNA replication/repair). Use null if not supported.'
            ),
        },
        'drug_susc_impact': _nullable_string(
            f'Impact on {organism_label} drug susceptibility (one or two concise sentences).'
        ),
        'infection_impact': _nullable_string(
            f'Impact on {organism_label} infection (one or two concise sentences).'
        ),
        'essential_in_vitro': _nullable_bool(
            f'Whether the gene is essential for {organism_label} survival in vitro.'
        ),
        'essential_in_vivo': _nullable_bool(
            f'Whether the gene is essential for {organism_label} survival in vivo.'
        ),
    }


def _identity_properties(organism_profile=None):
    locus_description = 'The gene locus identifier as supplied for this annotation.'
    if organism_profile is not None:
        locus_description = (
            f'The gene locus identifier for {organism_profile.canonical_name}; '
            f'must match this profile regex: {organism_profile.locus_regex}'
        )
    return {
        'gene_id': {
            'type': 'string',
            'description': locus_description,
        },
        'name': {
            'type': 'string',
            'description': (
                'The abbreviated name or symbol of the gene. If no distinct gene name is '
                'available, use the gene_id.'
            ),
        },
    }


def build_json_schema(organism_profile=None, *, require_biology=False, aggregate=False):
    organism_label = (
        organism_profile.species_name if organism_profile is not None else 'the organism'
    )
    required = ['gene_id', 'name']
    if require_biology:
        required += list(BIOLOGY_FIELDS)
    properties = {
        **_identity_properties(organism_profile),
        **_biology_properties(organism_label),
    }
    if aggregate:
        properties['annotation_notes'] = _nullable_string(
            'Transparency notes for curators: papers analyzed, literature strength, fields left '
            'unknown due to insufficient evidence, limitations, conflicts, and caveats.'
        )
        required.append('annotation_notes')
    return {
        'type': 'object',
        'properties': properties,
        'required': required,
        'additionalProperties': False,
    }


json_schema_section = build_json_schema()
json_schema_default = build_json_schema(require_biology=True)
json_schema_aggregate = build_json_schema(require_biology=True, aggregate=True)

# section field extraction prompt
prompt1_tmpl = '''
Using ONLY the supplied excerpt, return a JSON object for {5} gene {0}
(named {1}).

Section type: {3}
{4}

Rules:
- Always set gene_id and name exactly as supplied above.
- Include every biology field key listed below. Use JSON null for any field this excerpt does
  NOT explicitly support. Do not guess, infer from gene class, or use general organism knowledge.
- Do not use empty strings for unknown fields; use null.
- For essential_in_vitro and essential_in_vivo, use true or false only when this excerpt reports
  direct experimental evidence (e.g., deletion, transposon, CRISPRi). Otherwise use null.
- Prefer null over weak or speculative statements.

Fields: function, functional_category, drug_susc_impact, infection_impact, essential_in_vitro,
essential_in_vivo.

Excerpt:
{2}
'''

# json consensus prompt
prompt2_tmpl = '''
The following candidate JSON objects were generated from the same excerpt with different models.
Each candidate uses null for fields not supported by that excerpt.

Return one consensus JSON object with the same keys. Per field:
- If every candidate is null, output null.
- If only one candidate has a non-null value and the others are null, output that value.
- If two or more non-null candidates agree, output their shared value.
- If non-null candidates conflict (including true vs false), output null.

Never invent information not present in the candidates. Do not replace null with a guess.

Section type: {3}

First candidate: {0}

Second candidate: {1}

Third candidate: {2}
'''

# json aggregation prompt
prompt3_prefix = '''
The following JSON objects describe the same gene from different paper sections. Each object uses
null for fields that section did not support. Objects are labeled with PMID and literature
relevance score (higher = more relevant to this gene).

Aggregate into one final annotation:
- For each field, synthesize only from non-null contributions. Prefer higher-relevance sources when
  harmonizing details.
- If no object supports a field, output null for that field (not empty string).
- If objects conflict, output null for that field and describe the conflict in annotation_notes.
- For booleans, require consistent experimental support; do not infer essentiality without evidence.
- Cite PMIDs inline for supported prose fields, e.g. "detail (PMID 12345)".

Fill annotation_notes using the literature-selection context when provided. State how many papers
were analyzed, literature strength, which annotation fields remain unknown (null) due to
insufficient evidence, limitations, and conflicts. Do not invent paper counts or PMIDs.

Supplied section objects:
'''


class LlmHandler:
    @staticmethod
    def json_regex_filter(
        gene_json, rv_ptrn='[Rr]v[0-9]{4}[ABc]?',
        name_ptrn='([a-z]{3}[a-zA-Z0-9.]*)|([PE_GRS]{2,7}[0-9A]{1,3})',
        organism_profile=None,
    ):
        locus_ptrn = organism_profile.locus_regex if organism_profile is not None else rv_ptrn
        if organism_profile is not None:
            name_ptrn = rf'[\w.\-:/]+|{locus_ptrn}'
        else:
            name_ptrn += '|' + locus_ptrn
        try:
            gene_info = json.loads(gene_json)
            gene_id = gene_info.get('gene_id') or gene_info.get('rv_id', '')
            if not re.fullmatch(locus_ptrn, gene_id):
                return False
            if not re.fullmatch(name_ptrn, gene_info.get('name', '')):
                return False
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    @staticmethod
    def normalize_response_json(gene_json, *, require_biology_keys=False, organism_profile=None):
        parsed = json.loads(gene_json)
        normalized = normalize_annotation_fields(
            parsed,
            require_biology_keys=require_biology_keys,
            organism_profile=organism_profile,
        )
        return json.dumps(normalized)

    def __init__(self, cache_dir='./.cache'):
        self.cache_dir = cache_dir

    def get_llm_aggregate_json(
        self, json_responses, pmids, model='gemma3:12b',
        json_schema=None, retry=True, literature_context=None,
        relevance_scores=None, organism_profile=None,
    ):
        json_schema = json_schema or build_json_schema(
            organism_profile, require_biology=True, aggregate=True,
        )
        prompt = prompt3_prefix
        if literature_context:
            prompt += f'\n\n{literature_context}\n'
        if relevance_scores is None:
            relevance_scores = [None] * len(json_responses)
        for pmid, json_response, relevance in zip(pmids, json_responses, relevance_scores):
            normalized = self.normalize_response_json(
                json_response,
                organism_profile=organism_profile,
            )
            relevance_label = (
                f'{relevance:.3f}' if relevance is not None else 'not available'
            )
            prompt += f'\n\nPMID {pmid} (relevance {relevance_label}): {normalized}'

        cached_response, cached_dur = self._read_cache(model, prompt, json_schema)
        if cached_response is not None:
            log.debug((
                f'Returning cached section-aggregation response ({len(cached_response)} chars)'
            ))
            return self.normalize_response_json(
                cached_response,
                require_biology_keys=True,
                organism_profile=organism_profile,
            ), cached_dur

        log.debug((
            f'Submitting section-aggregation job ({len(json_responses)} blurbs; total '
            f'{len(prompt)} chars) to LLM (model {model})'
        ))
        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                    },
                ],
                format=json_schema,
                options={
                    'temperature': 0,
                },
            )
            response_text = response['message']['content']
            duration_sec = response['total_duration'] / 1_000_000_000
            log.debug(
                f'Got response ({len(response_text)} chars) back from {model} in ' + \
                    utils.seconds_to_str(duration_sec)
            )
            response_text = self.normalize_response_json(
                response_text,
                require_biology_keys=True,
                organism_profile=organism_profile,
            )
            self._write_cache(model, prompt, json_schema, response_text, duration_sec)
        except KeyError as ke:
            if retry:
                return self.get_llm_aggregate_json(
                    json_responses, pmids, model=model, json_schema=json_schema,
                    retry=False, literature_context=literature_context,
                    relevance_scores=relevance_scores, organism_profile=organism_profile,
                )
            else:
                raise RuntimeError(f'Failed to get response back from {model}') from ke
        return response_text, duration_sec

    def get_llm_consensus_json(
        self, json1, json2, json3, model='gemma3:12b', json_schema=None,
        retry=True, section_type='unknown', organism_profile=None,
    ):
        json_schema = json_schema or build_json_schema(organism_profile)
        json1 = self.normalize_response_json(json1, organism_profile=organism_profile)
        json2 = self.normalize_response_json(json2, organism_profile=organism_profile)
        json3 = self.normalize_response_json(json3, organism_profile=organism_profile)
        prompt = prompt2_tmpl.format(json1, json2, json3, section_type)

        cached_response, cached_dur = self._read_cache(model, prompt, json_schema)
        if cached_response is not None:
            log.debug((
                f'Returning cached candidate-aggregation response ({len(cached_response)} chars)'
            ))
            return self.normalize_response_json(
                cached_response,
                organism_profile=organism_profile,
            ), cached_dur

        log.debug((
            f'Submitting candidate-aggregation job (length {len(prompt)} chars) to LLM (model ' + \
                f'{model})'
        ))
        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                    },
                ],
                format=json_schema,
                options={
                    'temperature': 0,
                },
            )
            response_text = response['message']['content']
            duration_sec = response['total_duration'] / 1_000_000_000
            log.debug(
                f'Got response ({len(response_text)} chars) back from {model} in ' + \
                    utils.seconds_to_str(duration_sec)
            )
            response_text = self.normalize_response_json(
                response_text,
                organism_profile=organism_profile,
            )
            self._write_cache(model, prompt, json_schema, response_text, duration_sec)
        except KeyError as ke:
            if retry:
                return self.get_llm_consensus_json(
                    json1, json2, json3, model=model, json_schema=json_schema, retry=False,
                    section_type=section_type, organism_profile=organism_profile,
                )
            else:
                raise RuntimeError(f'Failed to get response back from {model}') from ke
        return response_text, duration_sec

    def get_llm_gene_info_json(
        self, gene_id, gene_name, info_text, model, json_schema=None,
        retry=True, section_type='unknown', organism_profile=None,
    ):
        organism_profile = organism_profile or organisms.resolve_profile('mtb-h37rv')
        json_schema = json_schema or build_json_schema(organism_profile)
        section_hint = SECTION_HINTS.get(section_type, '')
        prompt = prompt1_tmpl.format(
            gene_id, gene_name, info_text, section_type, section_hint,
            organism_profile.canonical_name,
        )

        cached_response, cached_dur = self._read_cache(model, prompt, json_schema)
        if cached_response is not None:
            log.debug((
                f'Returning cached section-summary response ({len(cached_response)} chars)'
            ))
            return self.normalize_response_json(
                cached_response,
                organism_profile=organism_profile,
            ), cached_dur

        log.debug((
            f'Submitting section-summary job (length {len(prompt)} chars) to LLM (model {model})'
        ))
        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                    },
                ],
                format=json_schema,
                options={
                    'temperature': 0,
                },
            )
            response_text = response['message']['content']
            duration_sec = response['total_duration'] / 1_000_000_000
            log.debug(
                f'Got response ({len(response_text)} chars) back from {model} in ' + \
                    utils.seconds_to_str(duration_sec)
            )
            response_text = self.normalize_response_json(
                response_text,
                organism_profile=organism_profile,
            )
            self._write_cache(model, prompt, json_schema, response_text, duration_sec)
        except KeyError as ke:
            if retry:
                return self.get_llm_gene_info_json(
                    gene_id, gene_name, info_text, model, json_schema=json_schema, retry=False,
                    section_type=section_type, organism_profile=organism_profile,
                )
            else:
                raise RuntimeError(f'Failed to get response back from {model}') from ke
        return response_text, duration_sec

    def _get_file(self, model, prompt, json_schema):
        md5 = hashlib.md5(usedforsecurity=False)
        md5.update(model.encode(encoding='utf8'))
        md5.update(prompt.encode(encoding='utf8'))
        md5.update(json.dumps(json_schema).encode(encoding='utf8'))
        digest = md5.hexdigest()

        return os.path.join(self.cache_dir, 'llm_responses', digest[:3], digest[3:] + '.json')

    def _read_cache(self, model, prompt, json_schema):
        cache_path = self._get_file(model, prompt, json_schema)
        if not os.path.exists(cache_path):
            return None, None
        log.debug(f'Reading cached response for LLM {model}')
        with open(cache_path) as cache_file:
            cache_obj = json.load(cache_file)
            return cache_obj['response_text'], cache_obj['duration_sec']

    def _write_cache(self, model, prompt, json_schema, response_text, duration_sec):
        log.debug(f'Caching response from LLM {model}')
        cache_path = self._get_file(model, prompt, json_schema)

        cache_parent = os.path.dirname(cache_path)
        if not os.path.exists(cache_parent):
            os.makedirs(cache_parent, exist_ok=True)

        content = dict(
            duration_sec=duration_sec,
            response_text=response_text,
        )
        try:
            with open(cache_path, 'w') as cache_file:
                json.dump(content, cache_file)
            return True
        except Exception:
            log.exception('Error encountered while writing cache file')
