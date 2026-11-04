"""Qualification runner control checks. These do not qualify a native host."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('qualify_install', ROOT / 'scripts/qualify-install.py')
qualify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualify)


def test_failed_step_never_reports_pass(tmp_path, monkeypatch):
    runner = qualify.Runner(tmp_path, 'core', 10, False)
    monkeypatch.setattr(qualify, 'run_group', lambda *a, **kw:
                        type('Result', (), dict(returncode=124, timed_out=True))())
    with pytest.raises(RuntimeError, match='failed'):
        runner.run('timeout', ['unused'])
    report = json.loads((tmp_path / 'report.json').read_text())
    assert report['status'] == 'inconclusive'
    assert report['steps'][0]['status'] == 'error'
    assert report['steps'][0]['timed_out'] is True


def test_zero_exit_step_is_not_whole_case_pass(tmp_path):
    runner = qualify.Runner(tmp_path, 'core', 10, False)
    runner.run('startup', [sys.executable, '-c', 'print("started")'])
    assert runner.report['status'] == 'inconclusive'
    assert runner.report['steps'][0]['status'] == 'pass'
    assert (tmp_path / '00-startup.log').read_text().strip() == 'started'


@pytest.mark.parametrize('value', [{}, {'status': 'inconclusive'}, {'status': 'no_checks'}])
def test_missing_runtime_evidence_is_error(tmp_path, value):
    runner = qualify.Runner(tmp_path, 'formal', 10, False)
    evidence = tmp_path / 'result.json'
    evidence.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match='runtime evidence'):
        runner.check_json(evidence, lambda r: r.get('status') == 'pass')


def test_case_plan_covers_each_acceptance_flag():
    assert qualify.CASES['quickstart'] == ['--with-sim', '--with-riscv-gcc', '--with-cosim']
    assert qualify.CASES['all'] == ['--all']
    assert set(qualify.CASES) == {'core', 'sim', 'gcc', 'cosim', 'formal', 'gem5', 'quickstart', 'all'}


@pytest.mark.parametrize('args', [ ['--timeout', 'nan'], ['--timeout', '0'],
                                 ['--case', 'gcc', '--cold-scala'] ])
def test_invalid_run_stops_before_creating_output(tmp_path, args):
    out = tmp_path / 'absent'
    run = subprocess.run([sys.executable, ROOT / 'scripts/qualify-install.py',
                          '--out', out, *args], capture_output=True, text=True, timeout=10)
    assert run.returncode == 2
    assert not out.exists()
