import json
import logging
import os
import re
import xml.etree.ElementTree as ET

import http_
import papers
import utils

logging.basicConfig(format='%(asctime)s %(levelname).1s | %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'

search_url_tmpl = base_url + 'esearch.fcgi?db=pmc&retmax=5000&retmode=json&term={term}'
search_term_locus_tmpl = '{locus}[title]+OR+{locus}[abstract]'
search_term_name_tmpl = (
    '(Mycobacterium+tuberculosis[abstract]+OR+Mycobacterium+tuberculosis[title])'
    '+AND+({name}[abstract]+OR+{name}[title])'
)

fetch_url_tmpl = base_url + 'efetch.fcgi?db=pmc&id={id}'

class PmcPaperManager(papers.PaperManager):
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

    def __init__(self, cache_dir):
        super().__init__(cache_dir)
        log.info(f'Using dir {cache_dir} for caching PMC papers')
        self.throttler = http_.Throttler()

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
        try:
            with open(abstrct_path, 'r', encoding='utf8') as abstrct_file:
                return re.sub(r'\n+', r'\n', abstrct_file.read())
        except FileNotFoundError:
            return None

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
        try:
            with open(discusn_path, 'r', encoding='utf8') as discusn_file:
                return re.sub(r'\n+', r'\n', discusn_file.read())
        except FileNotFoundError:
            return None

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
        try:
            with open(methods_path, 'r', encoding='utf8') as methods_file:
                return re.sub(r'\n+', r'\n', methods_file.read())
        except FileNotFoundError:
            return None

    def get_pmc_ids(self, gene, name):
        log.info(f'Searching PubMed Central for gene {gene}')

        search_term_locus = search_term_locus_tmpl.format(locus=gene)
        search_url1 = search_url_tmpl.format(term=search_term_locus)

        log.debug(f'Searching PubMed Central by gene locus {gene}')
        response1 = self.throttler.get(search_url1, base_url)
        result1 = json.loads(response1.text)
        idlist1 = result1['esearchresult']['idlist']
        log.debug(
            f'Found {len(idlist1)} paper{utils.s_if_plural(idlist1)} by locus for gene {gene}'
        )

        if name == gene:
            log.debug(f'No name available for gene {gene}; moving on with obtained papers')
            return idlist1

        log.debug(f'Searching PubMed Central by gene name {name}')

        search_term_name = search_term_name_tmpl.format(name=name)
        search_url2 = search_url_tmpl.format(term=search_term_name)

        response2 = self.throttler.get(search_url2, base_url)
        result2 = json.loads(response2.text)
        idlist2 = result2['esearchresult']['idlist']
        log.debug(f'Found {len(idlist2)} papers by name ({name}) for gene {gene}')

        combined = list(set(idlist1 + idlist2))

        if len(combined) < 3:
            log.warning(
                f'Found only {len(combined)} paper{utils.s_if_plural(combined)} for gene {gene}'
            )
        else:
            log.debug(
                f'That makes total of {len(combined)} paper{utils.s_if_plural(combined)} for ' + \
                    f'gene {gene}'
            )

        return combined

    def get_pmid(self, pmc_id):
        if pmc_id.startswith('PMC'):
            pmc_id = pmc_id[3:]
        article_xml = self._get_article_xml(pmc_id)
        article_meta = article_xml.find('front').find('article-meta')
        try:
            return article_meta.find('article-id[@pub-id-type="pmid"]').text
        except AttributeError as ae:
            log.exception(f'Failed PMID fetch for paper PMC{pmc_id}')

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
        try:
            with open(results_path, 'r', encoding='utf8') as results_file:
                return re.sub(r'\n+', r'\n', results_file.read())
        except FileNotFoundError:
            return None

    def is_relevant(self, pmc_id, gene, name):
        abstract = self.get_abstract(pmc_id)
        if abstract is None:
            return False

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
            gene_in_results = gene in results or name.lower() in abstract.lower()lsp
            excl_in_results = any(re.search(p, results) for p in self.species_excl_patterns)

            if not species_in_results or not gene_in_results or excl_in_results:
                return False

        return True

    def save_gene_pmc_ids(self, gene, pmc_ids):
        log.debug(
            f'Recording {len(pmc_ids)} paper{utils.s_if_plural(pmc_ids)} relevant to gene {gene}'
        )
        gene_pmc_ids_path = os.path.join(self.mapping_dir, f'{gene}.txt')
        with open(gene_pmc_ids_path, 'w', encoding='utf8') as gene_pmc_ids_file:
            gene_pmc_ids_file.write('\n'.join(pmc_ids))
            gene_pmc_ids_file.write('\n')

    def _download(self, pmc_id):
        log.debug(f'Downloading paper PMC{pmc_id} from PubMed Central')
        fetch_url = fetch_url_tmpl.format(id=pmc_id)

        response = self.throttler.get(fetch_url, base_url)

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
        try:
            self._save_section(
                article_xml.find('front').find('article-meta').find('abstract'),
                os.path.join(self.abstrct_dir, f'PMC{pmc_id}_abstract.txt')
            )
        except AttributeError as ae:
            log.debug(f'Paper PMC{pmc_id} missing abstract')
            return

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
                try:
                    section_type = section.find('title').text.lower()
                except AttributeError as ae:
                    log.info(
                        f'Paper PMC{pmc_id} has untitled body section; we may miss valid data'
                    )
                    continue

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
