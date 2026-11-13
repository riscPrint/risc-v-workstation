"""Fast tests for the native example's comparison summary."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('vex_check_isa', ROOT / 'examples/vexriscv/rvw/check-isa.py')
check_isa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_isa)


@pytest.mark.parametrize('status,complete,code,expected', [
    ('match', True, 0, 0), ('match', False, 0, 1),
    ('mismatch', True, 1, 1), ('inconclusive', False, 3, 1)])
def test_summary_requires_complete_matches(tmp_path, monkeypatch, status, complete, code, expected):
    manifest = tmp_path / 'jobs.jsonl'
    manifest.write_text(json.dumps(dict(elf='test.elf', out='run')) + '\n')
    report = dict(status=status, trace_complete=complete)
    def run(command, **kwargs):
        assert command[3:5] == ['cosim', 'check']
        assert '--platform' in command
        return SimpleNamespace(returncode=code, stdout=json.dumps(report), stderr='')
    monkeypatch.setattr(check_isa, 'run_group', run)
    out = tmp_path / 'summary.json'
    assert check_isa.compare(manifest, out) == expected
    assert json.loads(out.read_text())['counts'] == {status: 1}


def test_empty_campaign_cannot_match(tmp_path):
    manifest = tmp_path / 'empty'
    manifest.write_text('')
    assert check_isa.compare(manifest, tmp_path / 'summary.json') == 1


@pytest.mark.parametrize('core', ['vexriscv', 'vexiiriscv'])
def test_private_lock_in_launcher(core):
    script = (ROOT / f'examples/{core}/rvw/run.sh').read_text()
    assert '"${RVW_VEX_LOCK:-vex}"' in script

@pytest.mark.parametrize('references,expected', [
    ({'spike': {'status': 'match', 'trace_complete': True},
      'sail': {'status': 'match', 'trace_complete': True}}, 0),
    ({'spike': {'status': 'match', 'trace_complete': True}}, 1),
    ({'spike': {'status': 'match', 'trace_complete': True},
      'sail': {'status': 'match', 'trace_complete': False}}, 1),
])
def test_adjudication_requires_both_complete_references(tmp_path, monkeypatch, references, expected):
    manifest = tmp_path/'jobs.jsonl'
    manifest.write_text(json.dumps(dict(elf='test.elf', out='run'))+'\n')
    def run(command, **kwargs):
        assert command[3:5] == ['cosim', 'adjudicate']
        return SimpleNamespace(returncode=0, stdout=json.dumps(dict(status='match', references=references)), stderr='')
    monkeypatch.setattr(check_isa, 'run_group', run)
    assert check_isa.compare(manifest, tmp_path/'report.json', adjudicate=True) == expected
