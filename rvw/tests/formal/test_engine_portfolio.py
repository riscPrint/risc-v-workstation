import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.formal import portfolio as p


def plan(tmp_path):
    source = tmp_path / 'model.sv'
    source.write_text('module top(input clk); always @(posedge clk) assert(1); endmodule')
    return {'top': 'top', 'sources': [{'path': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
            'engines': ['abc:pdr', 'aiger:avy']}


def test_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(p.shutil, 'which', lambda _: None)
    r = p.race(plan(tmp_path), tmp_path, tmp_path / 'out')
    assert r['status'] == 'inconclusive'
    assert all(x['status'] == 'not_installed' for x in r['rows'])


def test_disagreement(tmp_path, monkeypatch):
    monkeypatch.setattr(p.shutil, 'which', lambda _: __file__)
    def run(cmd, **kwargs):
        if cmd[0] == 'yosys':
            (Path(kwargs['cwd']) / 'design.json').write_text('{"modules":{"top":{"cells":{"a":{"type":"$assert"}}}}}')
            return SimpleNamespace(stdout='', stderr='', returncode=0, timed_out=False)
        verdict = 'FAIL' if 'avy' in str(kwargs['cwd']) else 'PASS'
        return SimpleNamespace(stdout=f'DONE ({verdict}, rc=0)', stderr='', returncode=2 if verdict == 'FAIL' else 0, timed_out=False)
    monkeypatch.setattr(p, 'run_group', run)
    r = p.race(plan(tmp_path), tmp_path, tmp_path / 'out', cross_check=True)
    assert r['status'] == 'inconclusive' and r['cross_check'] == 'disagree'


def test_bounded_is_not_proof():
    assert p.parse_status('sby', 'DONE (PASS, rc=0)', 0, 'bmc') == 'bounded_pass'
    assert p.parse_status('sby', 'DONE (PASS, rc=0)', -11, 'prove') == 'error'
    assert p.parse_status('ebmc', '{"properties":[{"status":"PROVED up to bound 20"}]}', 0, 'bmc') == 'bounded_pass'


def test_hash_mismatch(tmp_path):
    m = plan(tmp_path)
    m['sources'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='hash mismatch'):
        p.race(m, tmp_path, tmp_path / 'out')


def test_ebmc_partial_proof_is_bounded():
    import json
    text = json.dumps({'properties': [{'status': 'PROVED'}, {'status': 'PROVED up to bound 10'}]})
    assert p.parse_status('ebmc', text, 10, 'prove') == 'bounded_pass'
    assert p.parse_status('ebmc', '{"properties":[]}', 0, 'prove') == 'inconclusive'
    assert p.parse_status('ebmc', '{"properties":[{"status":"ASSUMED"}]}', 0, 'prove') == 'inconclusive'


def test_no_checks_cannot_prove(tmp_path, monkeypatch):
    monkeypatch.setattr(p.shutil, 'which', lambda _: __file__)
    def run(cmd, **kwargs):
        assert cmd[0] == 'yosys'
        (Path(kwargs['cwd']) / 'design.json').write_text('{"modules":{"top":{"cells":{}}}}')
        return SimpleNamespace(stdout='', stderr='', returncode=0, timed_out=False)
    monkeypatch.setattr(p, 'run_group', run)
    r = p.race(plan(tmp_path), tmp_path, tmp_path / 'out')
    assert r['status'] == 'inconclusive' and r['reason'] == 'no_checks'


def test_uncertified_assumptions_cannot_earn_portfolio_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(p.shutil, 'which', lambda _: __file__)
    def run(cmd, **kwargs):
        if cmd[0] == 'yosys':
            (Path(kwargs['cwd']) / 'design.json').write_text('{"modules":{"top":{"cells":{"a":{"type":"$assert"},"e":{"type":"$assume"}}}}}')
        return SimpleNamespace(stdout='DONE (PASS, rc=0)', stderr='', returncode=0, timed_out=False)
    monkeypatch.setattr(p, 'run_group', run)
    r = p.race(plan(tmp_path), tmp_path, tmp_path / 'out', cross_check=True)
    assert r['status'] == 'inconclusive' and r['proof_kind'] == 'none'
    assert r['environment_check'] == 'activation_not_checked'


def test_ebmc_receives_original_aiger_bytes(tmp_path, monkeypatch):
    import json
    source = tmp_path / 'input.aag'
    source.write_bytes(b'aag 1 1 0 1 0\n2\n0\n')
    m = {'top': 'top', 'sources': [{'path': source.name, 'format': 'aiger',
          'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}], 'engines': ['ebmc']}
    monkeypatch.setattr(p.shutil, 'which', lambda _: __file__)
    def run(cmd, **kwargs):
        cwd = Path(kwargs['cwd'])
        if cmd[0] == 'yosys':
            (cwd / 'design.json').write_text('{"modules":{"top":{"cells":{"a":{"type":"$assert"}}}}}')
        else:
            assert Path(cmd[1]).read_bytes() == source.read_bytes()
            assert cmd[1].endswith('.aig')
            assert '--top' not in cmd
            (cwd / 'ebmc-result.json').write_text(json.dumps({'properties': [{'status': 'PROVED'}]}))
        return SimpleNamespace(stdout='', stderr='', returncode=0, timed_out=False)
    monkeypatch.setattr(p, 'run_group', run)
    r = p.race(m, tmp_path, tmp_path / 'out')
    assert r['status'] == 'pass'
    assert r['rows'][0]['input_format'] == 'aiger_native'
