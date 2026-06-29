import json
from unittest.mock import patch

import pandas as pd

from autoannotation import ortholog_lookup
from autoannotation.orthology import OrthologHit


def test_ortholog_lookup_cli_prints_hit(monkeypatch, capsys, tmp_path):
    mycobrowser_df = pd.DataFrame([
        {'Feature': 'CDS', 'Locus': 'Rv0001', 'Name': 'dnaA'},
    ])
    monkeypatch.setattr(
        ortholog_lookup.targets.organisms.gene_names.pd,
        'read_csv',
        lambda *args, **kwargs: mycobrowser_df,
    )
    fake_hit = OrthologHit(
        source_organism_code='mory',
        source_organism_name='Mycobacterium orygis',
        source_gene_id='MO_000001',
        source_gene_name='dnaA',
        score=507.0,
        lookup_source='kegg_ssdb',
    )
    with patch.object(ortholog_lookup.orthology, 'lookup_top_ortholog', return_value=fake_hit):
        exit_code = ortholog_lookup.main(['mtb-h37rv', 'Rv0001', '--cache-dir', str(tmp_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['kegg_organism_code'] == 'mtu'
    assert payload['kegg_query'] == 'mtu:Rv0001'
    assert payload['ortholog_top_hit']['source_gene_id'] == 'MO_000001'


def test_ortholog_lookup_cli_returns_nonzero_without_hit(monkeypatch, capsys, tmp_path):
    mycobrowser_df = pd.DataFrame([
        {'Feature': 'CDS', 'Locus': 'Rv0001', 'Name': 'dnaA'},
    ])
    monkeypatch.setattr(
        ortholog_lookup.targets.organisms.gene_names.pd,
        'read_csv',
        lambda *args, **kwargs: mycobrowser_df,
    )
    with patch.object(ortholog_lookup.orthology, 'lookup_top_ortholog', return_value=None):
        exit_code = ortholog_lookup.main(['--profile', 'mtb-h37rv', '--locus', 'Rv0001'])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload['ortholog_top_hit'] is None
    assert any(w['code'] == 'no_ortholog_hit' for w in payload['warnings'])
