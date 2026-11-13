"""Opt-in native project-adapter qualification."""
import json
import os
from pathlib import Path
import sys
import pytest
from rvw.common.proc import run_group
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'Uvm/examples/custom_bus/run.py'


@pytest.mark.skipif(os.environ.get('RVW_UVM_CUSTOM_NATIVE') != '1',
                    reason='set RVW_UVM_CUSTOM_NATIVE=1 for native custom-bus RTL controls')
def test_native_project_adapter_checks_good_and_corrupt_rtl(tmp_path):
    env = dict(os.environ)
    env.pop('PYTEST_CURRENT_TEST', None)
    result = run_group([sys.executable, str(SOURCE), '--out', str(tmp_path/'native')],
                       cwd=ROOT, env=env, capture=True, timeout=260)
    assert result.returncode == 0 and not result.timed_out, result.stdout + result.stderr
    report = json.loads((tmp_path/'native/qualification.json').read_text())
    assert [row['status'] for row in report['runs']] == ['pass', 'fail']
    assert all(row['expected_result_checked'] for row in report['runs'])
    assert report['runs'][0]['counts']['transfers'] == 82
