"""A failed fixture run must not publish an earlier run's result."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ooo_adapter_review', ROOT/'SpinalChecks/examples/ooo/adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


@pytest.mark.parametrize('code,timed_out', [(1, False), (0, True), (0, False)])
def test_failed_run_does_not_publish_stale_native_result(tmp_path, monkeypatch, code, timed_out):
    out = tmp_path/'out'
    native = out/'native/clean'
    native.mkdir(parents=True)
    old = json.dumps(dict(schema='rvw.run/1', status='pass'))
    (native/'result.json').write_text(old)
    (out/'result.json').write_text(old)
    monkeypatch.setattr('sys.argv', ['adapter.py', 'run', '--out', str(out), '--elf', 'fixture'])
    monkeypatch.setattr(adapter, 'run_group', lambda *args, **kwargs:
                        SimpleNamespace(returncode=code, timed_out=timed_out, stdout='failed', stderr=''))
    assert adapter.main() == 2
    assert not (out/'result.json').exists()


def test_successful_command_publishes_fresh_fixture_findings(tmp_path, monkeypatch):
    out = tmp_path/'out'
    monkeypatch.setattr('sys.argv', ['adapter.py', 'run', '--out', str(out), '--elf', 'fixture'])
    def execute(*args, **kwargs):
        native = Path(kwargs['env']['RVW_OOO_RUN_ROOT'])/'clean'
        native.mkdir(parents=True)
        (native/'result.json').write_text(json.dumps(dict(schema='rvw.run/1', status='fail')))
        return SimpleNamespace(returncode=0, timed_out=False, stdout='', stderr='')
    monkeypatch.setattr(adapter, 'run_group', execute)
    assert adapter.main() == 0
    assert json.loads((out/'result.json').read_text())['status'] == 'fail'
