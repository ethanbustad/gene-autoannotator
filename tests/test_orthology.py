import json
from pathlib import Path

import pytest

from autoannotation import orthology
from autoannotation.orthology import OrthologHit, lookup_top_ortholog, parse_ssdb_best_response


FIXTURE_DIR = Path(__file__).parent / 'fixtures' / 'kegg_ssdb'


def _load_fixture(name):
    return (FIXTURE_DIR / name).read_text(encoding='utf-8')


def test_parse_ssdb_best_skips_self_hit_and_returns_top_ortholog():
    html = _load_fixture('mtu_rv0001.html')

    hit = parse_ssdb_best_response(html, 'mtu')

    assert hit is not None
    assert hit.source_organism_code == 'mory'
    assert hit.source_gene_id == 'MO_000001'
    assert hit.score == 507.0
    assert hit.lookup_source == 'kegg_ssdb'


def test_parse_ssdb_best_returns_none_when_only_self_hit():
    html = '<html><A HREF="/entry/mtu:Rv9999">mtu:Rv9999</A></html>'

    assert parse_ssdb_best_response(html, 'mtu') is None


def test_lookup_top_ortholog_uses_cache(tmp_path):
    html = _load_fixture('mtu_rv0001.html')
    calls = {'count': 0}

    def fetch_html(_url):
        calls['count'] += 1
        return html

    hit1 = lookup_top_ortholog('mtu', 'Rv0001', cache_dir=tmp_path, fetch_html=fetch_html)
    hit2 = lookup_top_ortholog('mtu', 'Rv0001', cache_dir=tmp_path, fetch_html=fetch_html)

    assert hit1 == hit2
    assert calls['count'] == 1


def test_lookup_top_ortholog_returns_none_without_kegg_code(tmp_path):
    assert lookup_top_ortholog(None, 'Rv0001', cache_dir=tmp_path) is None
    assert lookup_top_ortholog('mtu', None, cache_dir=tmp_path) is None


def test_lookup_top_ortholog_handles_fetch_failure(tmp_path):
    def fetch_html(_url):
        raise ConnectionError('network down')

    assert lookup_top_ortholog('mtu', 'Rv0001', cache_dir=tmp_path, fetch_html=fetch_html) is None


def test_ortholog_hit_to_metadata():
    hit = OrthologHit(
        source_organism_code='msm',
        source_organism_name='Mycobacterium smegmatis',
        source_gene_id='MSMEG_0001',
        source_gene_name='dnaA',
        score=500.0,
        lookup_source='kegg_ssdb',
    )

    payload = hit.to_metadata()

    assert payload['source_organism_code'] == 'msm'
    assert payload['source_gene_id'] == 'MSMEG_0001'
    assert payload['score'] == 500.0


def test_profile_for_kegg_organism_uses_builtin_profile():
    profile = orthology.profile_for_kegg_organism('mtu')

    assert profile.profile_id == 'mtb-h37rv'
    assert profile.kegg_organism_code == 'mtu'


def test_profile_for_kegg_organism_builds_ad_hoc_for_msm():
    profile = orthology.profile_for_kegg_organism('msm')

    assert profile.profile_id == 'kegg-msm'
    assert profile.excluded_species_patterns == ()
