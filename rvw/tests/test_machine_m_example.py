"""The measured controller binding must reject another export."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast


def helper():
    path = Path(__file__).resolve().parents[2]/'examples/vexriscv/formal/machine_m.py'
    spec = importlib.util.spec_from_file_location('machine_m_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rejects_another_export_before_writing(tmp_path):
    source = tmp_path/'core.v'
    source.write_text('module VexRiscv; endmodule\n')
    with pytest.raises(ValueError, match='measured FormalMTop'):
        helper().prepare(source, tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_capture_keeps_source_and_all_transition_inputs(tmp_path):
    module = helper()
    source = tmp_path/'core.v'
    raw = b'module VexRiscv; endmodule\n'
    source.write_bytes(raw)
    module.RTL_SHA256 = hashlib.sha256(raw).hexdigest()
    plan = module.prepare(source, tmp_path/'out')
    assert source.read_bytes() == raw
    assert json.loads((tmp_path/'out/machine.json').read_text()) == plan
    captured = (tmp_path/'out/observed.v').read_text()
    assert 'assume' not in captured
    assert set(plan['checks']) == {'exception_entry', 'interrupt_entry', 'trap_return'}
    for check, selection in plan['checks'].items():
        assert set(selection['signals']) == set(module.RULES[check][0])
        assert f'observe_{check}_event <= !reset && (' in captured
    # Capture before-state. Read the actual updated core state for after-state.
    assert 'observe_trap_return_previous_mode_before <= CsrPlugin_mstatus_MPP;' in captured
    assert 'observe_trap_return_mode_after = CsrPlugin_privilege;' in captured


@pytest.mark.parametrize('status,code', [('bounded',3), ('inconclusive',3), ('failed',1)])
def test_run_exit_retains_failure_and_incomplete_scope(tmp_path, monkeypatch, status, code):
    module = helper()
    out = tmp_path/'out'
    def prepare(*args):
        out.mkdir()
        return {'checks': {'trap_return': {}}}
    monkeypatch.setattr(module, 'prepare', prepare)
    monkeypatch.setattr(module, 'run', lambda *args: {'rows': [
        {'check': 'trap_return', 'status': status, 'evidence': 'trap_return/check.sby'}]})
    monkeypatch.setattr(sys, 'argv', ['machine_m', '--rtl', 'core.v', '--out', str(out), '--run'])
    assert module.main() == code
    result = json.loads((out/'result.json').read_text())
    assert result['status'] == ('fail' if status == 'failed' else 'inconclusive')
    assert (out/result['rows'][0]['evidence']).relative_to(out).parts == (
        'trap_return', 'trap_return', 'check.sby')
