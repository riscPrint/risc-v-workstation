from hashlib import sha256
from types import SimpleNamespace
import pytest
from rvw.formal import aiger_live as live

pytestmark = pytest.mark.fast


def plan(tmp_path, fair=False):
    path = tmp_path / 'model.aag'
    path.write_text('aag 0 0 0 0 0 0 0 1' + (' 1' if fair else '') + '\n1\n0\n' + ('1\n' if fair else ''))
    return {'path': path.name, 'sha256': sha256(path.read_bytes()).hexdigest()}


def test_missing_and_mismatched_input(tmp_path, monkeypatch):
    monkeypatch.setattr(live.shutil, 'which', lambda _: None)
    p = plan(tmp_path)
    assert live.check(p, tmp_path, tmp_path / 'missing')['reason'] == 'not_installed'
    p['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='hash mismatch'):
        live.check(p, tmp_path, tmp_path / 'bad')


@pytest.mark.parametrize('code,text,timed_out,expected', [
    (20, 'UNSAT\n0\n', False, 'safe'), (10, 'SAT\n1\nb0\n.\n', False, 'unsafe'),
    (30, 'UNKNOWN\n', False, 'inconclusive'), (0, 'UNSAT\n', False, 'error'),
    (20, 'SAT\n', False, 'error'), (20, 'SAT\nUNSAT\n', False, 'error'),
    (20, 'UNSAT\n', True, 'timeout')])
def test_native_status_and_exit_pair(tmp_path, monkeypatch, code, text, timed_out, expected):
    path = tmp_path / 'model.aag'
    path.write_text('input')
    monkeypatch.setattr(live, 'run_group', lambda *a, **kw: SimpleNamespace(
        stdout=text, stderr='', returncode=code, timed_out=timed_out))
    assert live.native(path, tmp_path / 'run', 'ic3', 'rIC3', 1)['status'] == expected


@pytest.mark.parametrize('guard,expected', [('safe', 'inconclusive'), ('error', 'inconclusive'), ('unsafe', 'pass')])
def test_native_proof_needs_fairness_feasibility(tmp_path, monkeypatch, guard, expected):
    monkeypatch.setattr(live.shutil, 'which', lambda _: __file__)
    stages = iter(['safe', guard])
    monkeypatch.setattr(live, 'native', lambda *a: {'status': next(stages)})
    r = live.check(plan(tmp_path, True), tmp_path, tmp_path / 'out')
    assert r['status'] == expected
    assert len(r['stages']) == 2
    if expected == 'inconclusive':
        assert r['proof_kind'] == 'none'


def test_k_bound_is_not_a_liveness_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(live.shutil, 'which', lambda _: __file__)
    monkeypatch.setattr(live, 'native', lambda *a: {'status': 'unsafe'})
    r = live.check(plan(tmp_path), tmp_path, tmp_path / 'out', method='k-live')
    assert r['status'] == 'inconclusive' and r['reason'] == 'k_bound_reached'
    assert r['proof_kind'] == 'none'


def test_command_and_mcp_registration():
    from rvw.cli import build_parser
    from rvw.formal.commands.aiger_live import mcp_tools
    args = build_parser().parse_args(['formal', 'aiger-live', '--manifest', 'plan.json', '--out', 'out'])
    assert args.method == 'l2s' and args.k == 2
    assert [t.name for t in mcp_tools()] == ['formal_aiger_live']
