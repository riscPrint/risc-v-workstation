"""External CDC observations stay bound to the same frozen request."""
import json
from pathlib import Path
import pytest
from rvw.common.proc import Result
from rvw.lint import compare


def fake_response(monkeypatch, status='pass', digest=True):
    def run(argv, **kwargs):
        import hashlib
        request = Path(argv[1])
        response = dict(mode=json.loads(request.read_text()).get('mode'), schema='rvw.cdc-adapter-response/1', status=status, tool_version='fake 1',
                        request_sha256=hashlib.sha256(request.read_bytes()).hexdigest() if digest else 'wrong')
        Path(argv[2]).write_text(json.dumps(response))
        return Result(0)
    monkeypatch.setattr(compare, 'run_group', run)


@pytest.mark.parametrize('digest', [True,False])
def test_adapter_identity(tmp_path, monkeypatch, digest):
    fake_response(monkeypatch,digest=digest)
    r = compare.adapter('/fake', {'case':'reference'}, tmp_path / 'adapter', 1)
    assert r['status'] == ('pass' if digest else 'inconclusive')
    assert (tmp_path / 'adapter' / 'request.json').exists()


@pytest.mark.parametrize('status', ['clean', None, True])
def test_unknown_adapter_verdict(tmp_path, monkeypatch, status):
    fake_response(monkeypatch,status=status)
    assert compare.adapter('/fake', {}, tmp_path / 'adapter', 1)['status'] == 'inconclusive'


def test_adapter_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(compare, 'run_group',lambda *a,**k:Result(124,timed_out=True))
    assert compare.adapter('/fake',{},tmp_path / 'adapter',1)['status'] == 'inconclusive'


def test_pinned_suite_sources():
    import hashlib
    root = Path(__file__).resolve().parents[2] / 'SpinalChecks' / 'examples' / 'cdc'
    plan = json.loads((root / 'suite.json').read_text())
    assert len(plan['cases']) == 10
    for case in plan['cases']:
        spec = json.loads((root / case['manifest']).read_text())
        hashes = [hashlib.sha256((root / p).read_bytes()).hexdigest() for p in spec['verilog']]
        assert hashes == case['source_sha256']
        assert case['expected'] == ('fail' if case['id'].endswith('_fault') else 'pass')


def test_bmc_adapter_cannot_claim_short_prefix(tmp_path, monkeypatch):
    import hashlib
    def run(argv, **kwargs):
        request = Path(argv[1])
        Path(argv[2]).write_text(json.dumps(dict(schema='rvw.cdc-adapter-response/1',
            mode='bmc',status='pass',tool_version='fake',reached_depth=2,
            request_sha256=hashlib.sha256(request.read_bytes()).hexdigest())))
        return Result(0)
    monkeypatch.setattr(compare,'run_group',run)
    r = compare.adapter('/fake',dict(mode='bmc',depth=10),tmp_path / 'adapter',1)
    assert r['status'] == 'inconclusive'
    assert 'shorter' in r['reason']


@pytest.mark.parametrize('observed,expected,qualification', [
    ('pass','pass','matches_on_suite'),
    ('fail','pass','mismatch'),
    ('pass','fail','mismatch'),
    ('unknown','pass','inconclusive'),
])
def test_suite_oracle_is_independent(tmp_path, monkeypatch, capsys, observed, expected, qualification):
    from argparse import Namespace
    import hashlib
    source = tmp_path / 'source.sv'; source.write_text('// exported fixture')
    spec = tmp_path / 'spec.json'
    spec.write_text(json.dumps(dict(schema='rvw.cdc-protocol/1',kind='reset_release',
                                    top='Design',verilog=['source.sv'])))
    manifest = tmp_path / 'suite.json'
    manifest.write_text(json.dumps(dict(schema='rvw.cdc-bench/1',cases=[dict(
        id='reference',manifest='spec.json',expected=expected,
        source_sha256=[hashlib.sha256(source.read_bytes()).hexdigest()])])))
    def native(args):
        root = Path(args.out); root.mkdir()
        (root / 'result.json').write_text(json.dumps(dict(status=observed,proof_kind='unbounded')))
    monkeypatch.setattr(compare.protocol,'run',native)
    out = tmp_path / 'out'
    compare.run(Namespace(benchmark=str(manifest),out=str(out),depth=24,mode='prove',
                          engine='abc:pdr',timeout=1,json=True))
    r = json.loads((out / 'result.json').read_text())
    assert r['qualification']['native'] == qualification
    assert r['commercial_comparison'] == 'not_run'
