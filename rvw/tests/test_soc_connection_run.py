import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from rvw.soc import connection_run

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('transfer,activation,timed_out,expected', [
    ('pass','fail',False,'proven'), ('pass','pass',False,'inconclusive'),
    ('pass','fail',True,'inconclusive'), ('fail','fail',False,'fail')])
def test_contract_needs_transfer_and_activation(tmp_path, monkeypatch, transfer, activation, timed_out, expected):
    def run(command, **kwargs):
        out = Path(command[command.index('--out')+1]); out.mkdir()
        campaign = dict(proof_kind='unbounded', observations={
            'transfer':dict(status=transfer,returncode=0 if transfer=='pass' else 1,proof_kind='unbounded'),
            'activation':dict(status=activation,returncode=1 if activation=='fail' else 0)})
        row = dict(status='proven' if transfer=='pass' else 'contradicted',campaign=campaign)
        (out/'result.json').write_text(json.dumps(dict(connections=[row])))
        assert '--run' in command and '--proof-mode' in command
        return SimpleNamespace(returncode=1,timed_out=timed_out)
    monkeypatch.setattr(connection_run,'run_group',run)
    report = connection_run.run('design.db','connections.json',tmp_path/'out')
    assert report['status'] == expected


def test_missing_result_is_inconclusive(tmp_path, monkeypatch):
    monkeypatch.setattr(connection_run,'run_group',lambda *a,**k: SimpleNamespace(returncode=2,timed_out=False))
    assert connection_run.run('db','manifest',tmp_path/'out')['status'] == 'inconclusive'


def test_database_created_by_prepare_is_analyzed(tmp_path, monkeypatch):
    from rvw.soc.verify import verify
    from rvw.query import db
    from rvw.lint import structural
    source = Path(__file__).resolve().parents[2]/'SpinalSoc/examples/vex/soc.json'
    visited = []
    class DB:
        def __init__(self, path):
            if not Path(path).is_file():
                raise db.QueryError('not prepared')
            visited.append(path)
        def close(self):
            pass
    monkeypatch.setattr(db,'DesignDB',DB)
    monkeypatch.setattr(structural,'analyze',lambda *a: dict(status='inconclusive',clock_count=2))
    import sys
    manifest = tmp_path/'verify.json'
    manifest.write_text(json.dumps(dict(schema='rvw.soc-verify/1',
        prepare=[sys.executable,'-c','from pathlib import Path; import sys; Path(sys.argv[1]).touch()',
                 '{out}/fresh.db'],checks={'cdc_rdc':{'database':'{out}/fresh.db'}})))
    result = verify(source,tmp_path/'out',manifest)
    row = next(r for r in result['checks'] if r['kind']=='cdc_rdc')
    assert row['ran'] and row['generated'] and row['result']=='inconclusive'
    assert visited == [str(tmp_path/'out/fresh.db')]


def test_prepare_steps_stop_on_error(tmp_path):
    from rvw.soc.verify import verify
    import sys
    source = Path(__file__).resolve().parents[2]/'SpinalSoc/examples/vex/soc.json'
    manifest = tmp_path/'verify.json'
    manifest.write_text(json.dumps(dict(schema='rvw.soc-verify/1', checks={}, prepare_steps=[
        [sys.executable,'-c','raise SystemExit(2)'],
        [sys.executable,'-c','raise AssertionError("must not run")']
    ])))
    result = verify(source,tmp_path/'out',manifest)
    assert result['status'] == 'inconclusive'
    assert not (tmp_path/'out/prepare-1.log').exists()
    assert all(not row['ran'] for row in result['checks'])
