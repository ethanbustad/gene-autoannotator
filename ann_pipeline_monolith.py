import argparse
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import cloudscraper as cs
import ollama
import pandas as pd

logging.basicConfig(format='%(asctime)s %(levelname).1s | %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

_COOLDOWN_SECONDS = 0.5
_TIMEOUT_SECONDS = 60

base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'

search_url_tmpl = base_url + 'esearch.fcgi?db=pmc&retmax=5000&retmode=json&term={term}'
search_term_locus_tmpl = '{locus}[title]+OR+{locus}[abstract]'
search_term_name_tmpl = (
    '(Mycobacterium+tuberculosis[abstract]+OR+Mycobacterium+tuberculosis[title])'
    '+AND+({name}[abstract]+OR+{name}[title])'
)

fetch_url_tmpl = base_url + 'efetch.fcgi?db=pmc&id={id}'

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

Supplied objects:'''

class LllmHandler:
    @staticmethod
    def get_llm_aggregate_json(
        json_responses, pmids, model='gemma3:12b', json_schema=json_schema_default
    ):
        prompt = prompt3_prefix
        for pmid, json_response in zip(pmids, json_responses):
            prompt += f'\n\nPMID {pmid}: ' + json_response
        log.debug((
            f'Submitting section-aggregation job ({len(json_responses)} blurbs; total '
            f'{len(prompt)} chars) to LLM (model {model})'
        ))

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
                _seconds_to_str(duration_sec)
        )
        return response_text, duration_sec

    @staticmethod
    def get_llm_consensus_json(
        json1, json2, json3, model='gemma3:12b', json_schema=json_schema_default
    ):
        prompt = prompt2_tmpl.format(json1, json2, json3)
        log.debug((
            f'Submitting candidate-aggregation job (length {len(prompt)} chars) to LLM (model ' + \
                f'{model})'
        ))
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
                _seconds_to_str(duration_sec)
        )
        return response_text, duration_sec

    @staticmethod
    def get_llm_gene_info_json(
        gene_id, gene_name, info_text, model, json_schema=json_schema_default
    ):
        prompt = prompt1_tmpl.format(gene_id, gene_name, info_text)
        log.debug((
            f'Submitting section-summary job (length {len(prompt)} chars) to LLM (model {model})'
        ))
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
                _seconds_to_str(duration_sec)
        )
        return response_text, duration_sec

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

class PaperManager:
    path_abstrct = 'abstracts'
    path_discusn = 'discussion'
    path_methods = 'methods'
    path_results = 'results'
    path_fulltxt = 'fulltxt'
    path_mapping = 'mapping'
    path_parsed = 'parsed'
    species_incl_patterns = (
        r'Mycobacterium\stuberculosis', r'M.\stuberculosis', r'M.\stb', 'MTB', 'Mtb', 'MTb', 'mTB'
    )
    species_excl_patterns = (
        r'Mycobacterium\ssmegmatis', r'M.\ssmegmatis', r'M.\ssmeg'
    )

    def __init__(self, cache_dir, scraper, throttler):
        self.cache_dir = PaperManager.init_dir(cache_dir, 'cache dir')
        self.scraper = scraper
        self.throttler = throttler
        self.abstrct_dir = PaperManager.init_dir(
            os.path.join(self.cache_dir, self.path_abstrct), 'abstract dir'
        )
        self.discusn_dir = PaperManager.init_dir(
            os.path.join(self.cache_dir, self.path_discusn), 'discussion dir'
        )
        self.fulltxt_dir = PaperManager.init_dir(
            os.path.join(self.cache_dir, self.path_fulltxt), 'full-text dir'
        )
        self.mapping_dir = PaperManager.init_dir(
            os.path.join(self.cache_dir, self.path_methods), 'mapping dir'
        )
        self.methods_dir = PaperManager.init_dir(
            os.path.join(self.cache_dir, self.path_methods), 'methods dir'
        )
        self.parsed_dir = PaperManager.init_dir(
            os.path.join(self.cache_dir, self.path_parsed), 'recordkeeping dir'
        )
        self.results_dir = PaperManager.init_dir(
            os.path.join(self.cache_dir, self.path_results), 'results dir'
        )
        log.info(f'Using dir {cache_dir} for caching papers')

    def get_abstract(self, pmc_id):
        abstrct_path = os.path.join(self.abstrct_dir, f'PMC{pmc_id}_abstract.txt')
        if not os.path.isfile(abstrct_path):
            parsed_path = os.path.join(self.parsed_dir, f'PMC{pmc_id}.txt')
            if os.path.isfile(parsed_path):
                log.warning(f'No abstract available for paper PMC{pmc_id}')
                return None
            log.debug(f'No cached abstract for paper PMC{pmc_id}')
            self._parse(pmc_id)
        else:
            log.debug(f'Using cached abstract for paper PMC{pmc_id}')
        with open(abstrct_path, 'r', encoding='utf8') as abstrct_file:
            return re.sub(r'\n+', r'\n', abstrct_file.read())

    def get_discussion(self, pmc_id):
        discusn_path = os.path.join(self.discusn_dir, f'PMC{pmc_id}_discussion.txt')
        if not os.path.isfile(discusn_path):
            parsed_path = os.path.join(self.parsed_dir, f'PMC{pmc_id}.txt')
            if os.path.isfile(parsed_path):
                log.debug(f'No discussion available for paper PMC{pmc_id}')
                return None
            log.debug(f'No cached discussion for paper PMC{pmc_id}')
            self._parse(pmc_id)
        else:
            log.debug(f'Using cached discussion for paper PMC{pmc_id}')
        with open(discusn_path, 'r', encoding='utf8') as discusn_file:
            return re.sub(r'\n+', r'\n', discusn_file.read())

    def get_methods(self, pmc_id):
        methods_path = os.path.join(self.methods_dir, f'PMC{pmc_id}_methods.txt')
        if not os.path.isfile(methods_path):
            parsed_path = os.path.join(self.parsed_dir, f'PMC{pmc_id}.txt')
            if os.path.isfile(parsed_path):
                log.debug(f'No methods available for paper PMC{pmc_id}')
                return None
            log.debug(f'No cached methods for paper PMC{pmc_id}')
            self._parse(pmc_id)
        else:
            log.debug(f'Using cached methods for paper PMC{pmc_id}')
        with open(methods_path, 'r', encoding='utf8') as methods_file:
            return re.sub(r'\n+', r'\n', methods_file.read())

    def get_pmid(self, pmc_id):
        if pmc_id.startswith('PMC'):
            pmc_id = pmc_id[3:]
        article_xml = self._get_article_xml(pmc_id)
        article_meta = article_xml.find('front').find('article-meta')
        return article_meta.find('article-id[@pub-id-type="pmid"]').text

    def get_results(self, pmc_id):
        results_path = os.path.join(self.results_dir, f'PMC{pmc_id}_results.txt')
        if not os.path.isfile(results_path):
            parsed_path = os.path.join(self.parsed_dir, f'PMC{pmc_id}.txt')
            if os.path.isfile(parsed_path):
                log.debug(f'No results available for paper PMC{pmc_id}')
                return None
            log.debug(f'No cached results for paper PMC{pmc_id}')
            self._parse(pmc_id)
        else:
            log.debug(f'Using cached results for paper PMC{pmc_id}')
        with open(results_path, 'r', encoding='utf8') as results_file:
            return re.sub(r'\n+', r'\n', results_file.read())

    @staticmethod
    def init_dir(dirpath, name):
        if os.path.isfile(dirpath):
            raise ValueError((
                f'The provided {name} is an existing regular file: {dirpath}; '
                'please provide a directory'
            ))
        elif not os.path.isdir(dirpath):
            log.debug(f'Making subcache {name} at {dirpath}')
            os.makedirs(dirpath)
        return dirpath

    def is_relevant(self, pmc_id, gene, name):
        abstract = self.get_abstract(pmc_id)
        species_in_abstract = any(re.search(p, abstract) for p in self.species_incl_patterns)
        gene_in_abstract = gene in abstract or name.lower() in abstract.lower()

        if not species_in_abstract or not gene_in_abstract:
            return False

        discussion = self.get_discussion(pmc_id)

        if discussion is not None:
            species_in_discussion = any(re.search(p, discussion) for p in self.species_incl_patterns)
            gene_in_discussion = gene in discussion or name.lower() in abstract.lower()

            if not species_in_discussion or not gene_in_discussion:
                return False

        results = self.get_results(pmc_id)

        if results is not None:
            species_in_results = any(re.search(p, results) for p in self.species_incl_patterns)
            gene_in_results = gene in results or name.lower() in abstract.lower()
            excl_in_results = any(re.search(p, results) for p in self.species_excl_patterns)

            if not species_in_results or not gene_in_results or excl_in_results:
                return False

        return True

    def save_gene_pmc_ids(self, gene, pmc_ids):
        log.debug(f'Recording {len(pmc_ids)} papers relevant to gene {gene}')
        gene_pmc_ids_path = os.path.join(self.mapping_dir, f'{gene}.txt')
        with open(gene_pmc_ids_path, 'w', encoding='utf8') as gene_pmc_ids_file:
            gene_pmc_ids_file.write('\n'.join(pmc_ids))
            gene_pmc_ids_file.write('\n')

    def _download(self, pmc_id):
        log.debug(f'Downloading paper PMC{pmc_id} from PubMed Central')
        fetch_url = fetch_url_tmpl.format(id=pmc_id)

        response = self.throttler.throttle(
            base_url,
            lambda: self.scraper.get(fetch_url, timeout=_TIMEOUT_SECONDS)
        )

        fulltxt_path = os.path.join(self.fulltxt_dir, f'PMC{pmc_id}.xml')
        with open(fulltxt_path, 'w', encoding='utf8') as fulltxt_file:
            fulltxt_file.write(response.text)

        return response.text

    def _get_article_xml(self, pmc_id):
        fulltxt_path = os.path.join(self.fulltxt_dir, f'PMC{pmc_id}.xml')
        if os.path.isfile(fulltxt_path):
            xml_tree = ET.parse(fulltxt_path)
            root = xml_tree.getroot()
        else:
            root = ET.fromstring(self._download(pmc_id))

        return root[0]

    def _parse(self, pmc_id):
        parsed_path = os.path.join(self.parsed_dir, f'PMC{pmc_id}.txt')
        if os.path.exists(parsed_path):
            log.debug(f'Paper PMC{pmc_id} already parsed')
            return
        log.debug(f'Parsing paper PMC{pmc_id}')

        article_xml = self._get_article_xml(pmc_id)

        # abstract
        self._save_section(
            article_xml.find('front').find('article-meta').find('abstract'),
            os.path.join(self.abstrct_dir, f'PMC{pmc_id}_abstract.txt')
        )

        # all other sections
        body = article_xml.find('body')
        if body is None:
            with open(parsed_path, 'w', encoding='utf8') as parsed_file:
                parsed_file.write('')
            log.debug(f'No paper body available for PMC{pmc_id}')
            return

        for section in body.findall('sec'):
            section_type = section.get('sec-type')
            if section_type is None:
                section_type = section.find('title').text.lower()

            if 'discussion' in section_type:
                log.debug(f'Saving discussion for paper PMC{pmc_id}')
                self._save_section(
                    section,
                    os.path.join(self.discusn_dir, f'PMC{pmc_id}_discussion.txt')
                )
            # if, not elif, since we may have combined sections
            if 'methods' in section_type or 'procedures' in section_type:
                log.debug(f'Saving methods for paper PMC{pmc_id}')
                self._save_section(
                    section,
                    os.path.join(self.methods_dir, f'PMC{pmc_id}_methods.txt')
                )
            # if, not elif, since we may have combined sections
            if 'results' in section_type:
                log.debug(f'Saving results for paper PMC{pmc_id}')
                self._save_section(
                    section,
                    os.path.join(self.results_dir, f'PMC{pmc_id}_results.txt')
                )

        with open(parsed_path, 'w', encoding='utf8') as parsed_file:
            parsed_file.write('')

    def _save_section(self, xml_element, filepath):
        with open(filepath, 'wb') as section_file: # b mode since ET.tostring with utf8 yields bytes
            section_file.write(ET.tostring(xml_element, encoding='utf8', method='text'))

class Throttler:
    def __init__(self, cooldown_seconds):
        self.cooldown_seconds = cooldown_seconds
        self.last_requests = {}
        self.verbosity = 0
        if cooldown_seconds <= 1:
            log.info(
                f'Using throttler to make no more than {1/cooldown_seconds:.0f} requests per second'
            )
        else:
            log.info(
                f'Using throttler to make no more than one request per {cooldown_seconds} seconds'
            )

    def throttle(self, label, throttled_function):
        if label in self.last_requests:
            time_passed = time.time() - self.last_requests[label]
            if time_passed < self.cooldown_seconds:
                wait_time = self.cooldown_seconds - time_passed
                log.debug(f'Slowing down requests: sleeping for {wait_time:.3f}s')
                time.sleep(wait_time)
        return_value = throttled_function()
        self.last_requests[label] = time.time()
        return return_value

def get_gene_annotation(gene, cache_dir='./.cache'):
    log.info(f'Starting annotation process for gene {gene}')
    start = time.time()
    scraper = cs.create_scraper()
    throttler = Throttler(_COOLDOWN_SECONDS)

    paper_manager = PaperManager(cache_dir, scraper, throttler)

    mycobrowser_df = pd.read_csv(
        '../published_data/Mycobacterium_tuberculosis_H37Rv_txt_v5.txt',
        sep='\t'
    )
    mycobrowser_df = mycobrowser_df.loc[
        mycobrowser_df['Feature'].eq('CDS'), :
    ].set_index(
        'Locus', drop=True
    ).sort_index()

    name = mycobrowser_df.at[gene, 'Name']

    pmc_ids = get_pmc_ids(gene, name, scraper=scraper, throttler=throttler)
    paper_manager.save_gene_pmc_ids(gene, pmc_ids)
    section_distillation_candidates = []
    section_distillations = []

    for pmc_id in pmc_ids:
        sections = []

        # filter based on established paper relevance criteria
        if not paper_manager.is_relevant(pmc_id, gene, name):
            log.info(f'Skipping paper PMC{pmc_id}: does not pass relevance checks for gene {gene}')
            continue
        else:
            log.info(f'Starting inference process for gene {gene} with paper PMC{pmc_id}')

        abstract = paper_manager.get_abstract(pmc_id)
        if abstract is not None:
            sections.append(('abstract', abstract))
        results = paper_manager.get_results(pmc_id)
        if results is not None:
            sections.append(('results', results))
        discussion = paper_manager.get_discussion(pmc_id)
        if discussion is not None and discussion != results:
            sections.append(('discussion', discussion))

        log.debug(f'Obtained {len(sections)} relevant sections for paper PMC{pmc_id}')

        for label, section in sections:
            log.debug(f'Starting processing for PMC{pmc_id} {label}')
            section_distillation_candidates_cur = []
            for model in ('mistral-nemo:12b', 'llama3:8b', 'gemma3:12b'):
                section_distillation_candidate, duration_sec = LllmHandler.get_llm_gene_info_json(
                    gene, name, section, model
                )
                section_distillation_candidates_cur.append(section_distillation_candidate)
                section_distillation_candidates.append((
                    f'PMC{pmc_id}', label, model, gene, name, section_distillation_candidate,
                    duration_sec
                ))
            section_distillation, duration_sec = LllmHandler.get_llm_consensus_json(
                section_distillation_candidates_cur[0], section_distillation_candidates_cur[1],
                section_distillation_candidates_cur[2], model='phi4:14b'
            )
            section_distillations.append((
                f'PMC{pmc_id}', label, 'phi4:14b', gene, name, section_distillation, duration_sec
            ))

    section_distillation_candidate_df = pd.DataFrame(
        section_distillation_candidates,
        columns=['PmcId', 'SectionType', 'Model', 'Gene', 'GeneName', 'Response', 'LlmDur'],
    )

    section_distillation_df = pd.DataFrame(
        section_distillations,
        columns=['PmcId', 'SectionType', 'Model', 'Gene', 'GeneName', 'Response', 'LlmDur'],
    )
    log.debug(' '.join((
        'Finished paper distillation by LLM with',
        str(len(section_distillation_candidate_df)),
        'total summaries generated for',
        str(len(section_distillation_df)),
        'total paper sections for gene',
        gene
    )))
    section_distillation_df.insert(
        1, 'PMID', section_distillation_df['PmcId'].map(paper_manager.get_pmid)
    )

    section_distillation_filtered_df = section_distillation_df.loc[
        section_distillation_df['Response'].map(LllmHandler.json_regex_filter),
        :
    ]
    log.debug(
        f'Filtered down to {len(section_distillation_filtered_df)} valid sections for gene {gene}'
    )

    gene_distillation, duration_sec = LllmHandler.get_llm_aggregate_json(
        section_distillation_filtered_df['Response'],
        section_distillation_filtered_df['PMID'],
        model='gemma3:12b'
    )
    duration = time.time() - start
    log.info(
        f'Finished annotation process for gene {gene} in {_seconds_to_str(duration)}'
    )

    return gene_distillation

def get_pmc_ids(gene, name, scraper=None, throttler=None):
    log.info(f'Searching PubMed Central for gene {gene}')
    if scraper is None:
        scraper = cs.create_scraper()
    if throttler is None:
        throttler = Throttler(_COOLDOWN_SECONDS)

    search_term_locus = search_term_locus_tmpl.format(locus=gene)
    search_url1 = search_url_tmpl.format(term=search_term_locus)

    log.debug(f'Searching PubMed Central by gene locus {gene}')
    response1 = throttler.throttle(
        base_url,
        lambda: scraper.get(search_url1, timeout=_TIMEOUT_SECONDS)
    )
    result1 = json.loads(response1.text)
    idlist1 = result1['esearchresult']['idlist']
    log.debug(f'Found {len(idlist1)} papers by locus for gene {gene}')

    if name == gene:
        log.debug(f'No name available for gene {gene}; moving on with obtained papers')
        return idlist1

    log.debug(f'Searching PubMed Central by gene name {name}')

    search_term_name = search_term_name_tmpl.format(name=name)
    search_url2 = search_url_tmpl.format(term=search_term_name)

    response2 = throttler.throttle(
        base_url,
        lambda: scraper.get(search_url2, timeout=_TIMEOUT_SECONDS)
    )
    result2 = json.loads(response2.text)
    idlist2 = result2['esearchresult']['idlist']
    log.debug(f'Found {len(idlist2)} papers by name ({name}) for gene {gene}')

    combined = list(set(idlist1 + idlist2))
    log.debug(f'That makes total of {len(combined)} papers for gene {gene}')

    return combined

def main(gene, cache_dir='./.cache'):
    gene_distillation = get_gene_annotation(gene, cache_dir=cache_dir)

    print(gene, json.dumps(gene_distillation, indent=2))

    return gene_distillation

def _seconds_to_str(total_seconds):
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    total_hours = total_minutes // 60
    hours = total_hours % 24
    total_days = total_hours // 24
    if total_days > 0:
        return f'{total_days:.0f}d, {hours:.0f}h, {minutes:.0f}m, {seconds:.1f}s'
    elif total_hours > 0:
        return f'{hours:.0f}h, {minutes:.0f}m, {seconds:.1f}s'
    elif total_minutes > 0:
        return f'{minutes:.0f}m, {seconds:.1f}s'
    else:
        return f'{seconds:.1f}s'

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
