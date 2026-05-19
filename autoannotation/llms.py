import hashlib
import json
import logging
import os
import re

import ollama

from . import utils

logging.basicConfig(format='%(asctime)s %(levelname).1s | %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

json_schema_default = {
    'type': 'object',
    'properties': {
        'rv_id': {
            'type': 'string',
            'description': (
                'The gene locus as identified in the H37Rv annotation; formatted as "Rv", four '
                'digits, then possibly an "A" or "c"'
            ),
        },
        'name': {
            'type': 'string',
            'description': (
                'The abbreviated name of the gene; should consist of 3-8 letters and/or digits, '
                'possibly with a "_" or "." included'
            ),
        },
        'function': {
            'type': 'string',
            'description': (
                'A description of what the product of this gene accomplishes for the cell (as '
                'short, concise prose of just one or two sentences)'
            ),
        },
        'functional_category': {
            'type': 'array',
            'items': {
                'type': 'string',
            },
            'minItems': 1,
            'description': 'One or more general cellular functions contributed to by this gene',
        },
        'drug_susc_impact': {
            'type': 'string',
            'description': (
                'Any impact the gene has on Mtb drug susceptibility (as short, concise prose of '
                'just one or two sentences)'
            ),
        },
        'infection_impact': {
            'type': 'string',
            'description': (
                'Any impact the gene has on Mtb infection (as short, concise prose of just one or '
                'two sentences)'
            ),
        },
        'essential_in_vitro': {
            'type': 'boolean',
            'description': (
                'Whether the gene is essential for Mtb survival in vitro (i.e., in artificial '
                'growth medium)'
            ),
        },
        'essential_in_vivo': {
            'type': 'boolean',
            'description': (
                'Whether the gene is essential for Mtb survival in vivo (i.e., in the context '
                'of an infection)'
            ),
        },
    },
    'required': [
        'rv_id',
        'name',
        'function',
        'functional_category',
        'drug_susc_impact',
        'infection_impact',
        'essential_in_vitro',
        'essential_in_vivo',
    ],
    'additionalProperties': False,
}

json_schema_aggregate = {
    **json_schema_default,
    'properties': {
        **json_schema_default['properties'],
        'annotation_notes': {
            'type': 'string',
            'description': (
                'Transparency notes for curators: how many papers were analyzed, whether '
                'the literature base was strong or weak, limitations, missing evidence, '
                'conflicts, and caveats. Do not repeat the full annotation fields here.'
            ),
        },
    },
    'required': json_schema_default['required'] + ['annotation_notes'],
}

prompt1_tmpl = '''
Using only the supplied information, return a JSON object describing the Mycobacterium
tuberculosis gene {0} (named {1}) with the following fields:
the Rv gene ID (as just supplied), the abbreviated gene name (as just supplied),
the function of the gene,
the gene's functional category (or multiple categories; e.g., cell wall, respiration,
growth regulation, virulence, DNA replication/repair, stress response),
impact on Mtb's drug susceptibility,
impact on Mtb infection,
whether the gene is essential for Mtb's survival in vitro,
and whether the gene is essential for Mtb's survival in vivo.

If any required information isn't supplied in the text, set that field to the empty string.

Use the following informational text to complete your JSON response:
{2}
'''

prompt2_tmpl = '''
The following candidate JSON objects were generated from the same underlying data but with
different generation methods. All methods involved a similar chance of error.
Return a consensus JSON object with the same fields as provided in each candidate, but with each
field containing the most likely true answer given the candidate answers provided. Where two of the
supplied candidates agree, assume their agreement reveals the truth.

First candidate: {0}

Second candidate: {1}

Third candidate: {2}
'''

prompt3_prefix = '''
The following candidate JSON objects were generated concerning the same gene but based off of
different source material. Return a JSON object aggregating the following supplied objects into a
single consensus output. If supplied objects supply different details for the same field, harmonize
those multiple points in the output response. If supplied objects directly contradict each other,
note that a disagreement exists and include the gist of each perspective. Keep responses as concise
as possible while still including all relevant details.

Cite sources as much as possible using the PMID provided with each object, with a format like
"interesting detail (PMID 00000)".

Fill annotation_notes using the literature-selection context below when provided. Summarize how
many papers were analyzed, whether the literature was abundant and high relevance or sparse and
weaker, important limitations, missing evidence, and confidence caveats. Do not invent paper counts.

Supplied objects:'''

class LlmHandler:
    @staticmethod
    def json_regex_filter(
        gene_json, rv_ptrn='[Rr]v[0-9]{4}[ABc]?',
        name_ptrn='([a-z]{3}[a-zA-Z0-9.]*)|([PE_GRS]{2,7}[0-9A]{1,3})'
    ):
        name_ptrn += '|' + rv_ptrn
        try:
            gene_info = json.loads(gene_json)
            if re.fullmatch(rv_ptrn, gene_info['rv_id']) and \
                    re.fullmatch(name_ptrn, gene_info['name']):
                return True
            else:
                return False
        except json.JSONDecodeError:
            return False

    def __init__(self, cache_dir='./.cache'):
        self.cache_dir = cache_dir

    def get_llm_aggregate_json(
        self, json_responses, pmids, model='gemma3:12b',
        json_schema=json_schema_aggregate, retry=True, literature_context=None,
    ):
        prompt = prompt3_prefix
        if literature_context:
            prompt += f'\n\n{literature_context}\n'
        for pmid, json_response in zip(pmids, json_responses):
            prompt += f'\n\nPMID {pmid}: ' + json_response

        cached_response, cached_dur = self._read_cache(model, prompt, json_schema)
        if cached_response is not None:
            log.debug((
                f'Returning cached section-aggregation response ({len(cached_response)} chars)'
            ))
            return cached_response, cached_dur

        log.debug((
            f'Submitting section-aggregation job ({len(json_responses)} blurbs; total '
            f'{len(prompt)} chars) to LLM (model {model})'
        ))
        try:
            response: ChatResponse = ollama.chat(
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
            duration_sec = response['total_duration'] / 1_000_000_000 # nanoseconds -> seconds
            log.debug(
                f'Got response ({len(response_text)} chars) back from {model} in ' + \
                    utils.seconds_to_str(duration_sec)
            )
            self._write_cache(model, prompt, json_schema, response_text, duration_sec)
        except KeyError as ke:
            if retry:
                return self.get_llm_aggregate_json(
                    json_responses, pmids, model=model, json_schema=json_schema,
                    retry=False, literature_context=literature_context,
                )
            else:
                raise RuntimeError(f'Failed to get response back from {model}') from ke
        return response_text, duration_sec

    def get_llm_consensus_json(
        self, json1, json2, json3, model='gemma3:12b', json_schema=json_schema_default, retry=True,
    ):
        prompt = prompt2_tmpl.format(json1, json2, json3)

        cached_response, cached_dur = self._read_cache(model, prompt, json_schema)
        if cached_response is not None:
            log.debug((
                f'Returning cached candidate-aggregation response ({len(cached_response)} chars)'
            ))
            return cached_response, cached_dur

        log.debug((
            f'Submitting candidate-aggregation job (length {len(prompt)} chars) to LLM (model ' + \
                f'{model})'
        ))
        try:
            response: ChatResponse = ollama.chat(
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
            duration_sec = response['total_duration'] / 1_000_000_000 # nanoseconds -> seconds
            log.debug(
                f'Got response ({len(response_text)} chars) back from {model} in ' + \
                    utils.seconds_to_str(duration_sec)
            )
            self._write_cache(model, prompt, json_schema, response_text, duration_sec)
        except KeyError as ke:
            if retry:
                return get_llm_consensus_json(
                    json1, json2, json3, model=model, json_schema=json_schema, retry=False,
                )
            else:
                raise RuntimeError(f'Failed to get response back from {model}') from ke
        return response_text, duration_sec

    def get_llm_gene_info_json(
        self, gene_id, gene_name, info_text, model, json_schema=json_schema_default, retry=True,
    ):
        prompt = prompt1_tmpl.format(gene_id, gene_name, info_text)

        cached_response, cached_dur = self._read_cache(model, prompt, json_schema)
        if cached_response is not None:
            log.debug((
                f'Returning cached section-summary response ({len(cached_response)} chars)'
            ))
            return cached_response, cached_dur

        log.debug((
            f'Submitting section-summary job (length {len(prompt)} chars) to LLM (model {model})'
        ))
        try:
            response: ChatResponse = ollama.chat(
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
            duration_sec = response['total_duration'] / 1_000_000_000 # nanoseconds -> seconds
            log.debug(
                f'Got response ({len(response_text)} chars) back from {model} in ' + \
                    utils.seconds_to_str(duration_sec)
            )
            self._write_cache(model, prompt, json_schema, response_text, duration_sec)
        except KeyError as ke:
            if retry:
                return self.get_llm_gene_info_json(
                    gene_id, gene_name, info_text, model, json_schema=json_schema, retry=False,
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
            os.makedirs(cache_parent, exist_ok=True) # prevent race condition issue with exist_ok

        content = dict(
            duration_sec=duration_sec,
            response_text=response_text,
        )
        try:
            with open(cache_path, 'w') as cache_file:
                json.dump(content, cache_file)
            return True
        except Exception as e:
            log.exception('Error encountered while writing cache file')
