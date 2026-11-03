"""A C1 pass with missing evidence must remain inconclusive."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / 'RiscvSim/tests/ordering'
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location('ordering_runner', DIRECTORY / 'run.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.mark.parametrize('extra', [
    {'inconclusive': 'missing RTL identity'},
    {'synthesized': True},
    {'wall_clock_timeout': True},
])
def test_runner_rejects_inconclusive_c1(tmp_path, monkeypatch, extra):
    def execute(command, **kwargs):
        if 'run-many' in command:
            manifest = Path(command[command.index('--manifest') + 1])
            for line in manifest.read_text().splitlines():
                job = json.loads(line)
                out = Path(job['out'])
                out.mkdir()
                (out / 'result.json').write_text(json.dumps(dict(
                    schema='rvw.run/1', status='pass', **extra)))
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(runner, 'run_group', execute)
    monkeypatch.setattr(sys, 'argv', ['run.py', '--out', str(tmp_path),
                                    '--seeds', '1', '--adapter', '/fake/adapter'])
    assert runner.main() == 3
    assert set(json.loads((tmp_path / 'summary.json').read_text())['dut']) == {'inconclusive'}
