"""Connection tables and graph boundary tests. No DUT proof is implied."""
import json

import pytest

from rvw.formal.connectivity import reverse_check
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
