"""Connection tables and graph boundary tests. No DUT proof is implied."""
import json

import pytest

from rvw.cli import main
from rvw.formal.connectivity import harness, reverse_check
from rvw.query.db import DesignDB
from rvw.soc.connectivity import load


pytestmark = pytest.mark.fast


@pytest.mark.parametrize('suffix,text', [
    ('.csv', 'source,destination,condition,delay,inversion\nio_a,io_result,io_loadValues,1,true\n'),
    ('.json', json.dumps({'connection': [dict(source='io_a', destination='io_result', condition='io_loadValues', delay=1, inversion=True)]})),
])
def test_table_normalization(tmp_path, suffix, text):
    path = tmp_path / ('connections' + suffix)
    path.write_text(text)
    assert load(path) == [dict(id='connection-1', kind='required', source='io_a',
                              destination='io_result', enable='io_loadValues', latency=1, inversion=True)]


def test_inversion_is_sampled_before_delay(gcd_db):
    db = DesignDB(gcd_db)
    try:
        text = harness(db, dict(kind='required', source='io_a', destination='io_result', latency=1, inversion=True))
        assert 'expected_0 <= ~p0;' in text
        assert '== expected_0' in text
    finally:
        db.close()


def test_reverse_finds_undeclared_input(gcd_db):
    db = DesignDB(gcd_db)
    try:
        rows = [dict(kind='required', source='io_a', destination='io_result')]
        report = reverse_check(db, rows)
        assert report['status'] == 'incomplete'
        assert any(r.get('driver') == 'io_b' for r in report['issues'])
        assert any(r['destination'] == 'io_resultIsValid' and 'no required source' in r['reason'] for r in report['issues'])
        assert reverse_check(db, rows, max_nodes=1)['status'] == 'incomplete'
        assert reverse_check(db, [dict(kind='required', source='missing', destination='io_result')])['status'] == 'incomplete'
    finally:
        db.close()


def test_csv_cli_captures_original_name(gcd_db, tmp_path):
    path = tmp_path / 'connections.csv'
    path.write_text('source,destination,delay,inversion\nio_a,io_result,1,false\n')
    out = tmp_path / 'report'
    assert main(['formal', 'connectivity', str(path), '--db', str(gcd_db), '--out', str(out)]) == 1
    report = json.loads((out / 'result.json').read_text())
    assert report['unproven'] == ['connection-1']
    assert report['contradicted'] == []
    assert report['reverse_check']['issues']


@pytest.mark.parametrize('text', [
    'source,destination,inversion\na,b,yes\n',
    'source,destination,delay,latency\na,b,1,1\n',
    'id,source,destination\na,b,c\na,c,d\n',
])
def test_bad_csv(tmp_path, text):
    path = tmp_path / 'bad.csv'
    path.write_text(text)
    with pytest.raises(ValueError):
        load(path)


def test_mcp_uses_positional_manifest(tmp_path):
    from rvw.formal.mcp_tools import _connectivity
    (tmp_path / 'result.json').write_text(json.dumps(dict(schema='rvw.connectivity/1', status='incomplete')))
    class Job:
        def run(self, argv):
            assert argv[5:] == ['--out', str(tmp_path), '--db', 'design.db', '--proof-mode', 'prove', 'table.csv', '--run']
            return 1
    assert _connectivity(Job(), manifest='table.csv', out=str(tmp_path), db='design.db', run=True, proof_mode='prove')['status'] == 'incomplete'


def test_soc_integration(gcd_db, tmp_path):
    from pathlib import Path
    from rvw.soc.check import check
    root = Path(__file__).resolve().parents[2]
    bindings = tmp_path / 'bindings.json'
    bindings.write_text(json.dumps(dict(schema='rvw.soc-bindings/1', signals=[], decoders=[], bridges=[])))
    table = tmp_path / 'connections.json'
    table.write_text(json.dumps({'connection': [dict(source='io_a', destination='io_result')]}))
    result = check(root / 'examples/vexriscv/soc.json', bindings, gcd_db, connections=table)
    assert result['status'] == 'inconclusive'
    assert result['connectivity']['connections'][0]['structural_status'] == 'dependency_found'
    assert result['connectivity']['reverse_check']['issues']
    assert len(result['connectivity']['database_sha256']) == 64


def test_value_proof_cannot_replace_structural_dependency(gcd_db,tmp_path,monkeypatch):
    path=tmp_path/'connections.json'
    path.write_text(json.dumps({'connection':[dict(id='missing_path',source='io_result',destination='io_a')]}))
    monkeypatch.setattr('rvw.formal.connectivity.campaign',lambda *a:dict(status='proven'))
    out=tmp_path/'out'
    assert main(['formal','connectivity',str(path),'--db',str(gcd_db),'--out',str(out),'--run'])==1
    row=json.loads((out/'result.json').read_text())['connections'][0]
    assert row['structural_status']=='dependency_absent'
    assert row['semantic_status']=='proven'
    assert row['status']=='incomplete'
