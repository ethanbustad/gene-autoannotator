import logging
import os

logging.basicConfig(format='%(asctime)s %(levelname).1s | %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

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

    def __init__(self, cache_dir):
        self.cache_dir = PaperManager.init_dir(cache_dir, 'cache dir')
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
