"""Keep the RV32IM history checks and their environment explicit."""
import hashlib
import importlib.util
from pathlib import Path

import pytest
from rvw.formal.machine_checks import generate

pytestmark = pytest.mark.fast


def helper(monkeypatch):
    path = Path(__file__).resolve().parents[2]/'examples/vexriscv/formal/machine_remaining.py'
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location('machine_remaining_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrong_export_is_rejected(tmp_path, monkeypatch):
    module = helper(monkeypatch)
    source = tmp_path/'core.v'; source.write_text('module VexRiscv; endmodule')
    with pytest.raises(ValueError, match='measured FormalMTop'):
        module.prepare(source, tmp_path/'capture')
    assert not (tmp_path/'capture').exists()
    with pytest.raises(ValueError, match='depth'):
        module.prepare(source,tmp_path/'invalid',depth=1)


def test_history_capture_and_rule_generation(tmp_path, monkeypatch):
    module = helper(monkeypatch)
    raw = b'module VexRiscv; endmodule\n'
    module.RTL_SHA256 = hashlib.sha256(raw).hexdigest()
    source = tmp_path/'core.v'; source.write_bytes(raw)
    capture = tmp_path/'capture'
    plan = module.prepare(source, capture)
    assert source.read_bytes() == raw
    assert set(plan['checks']) == {'csr_consistency','instruction_memory','flush_retirement','trap_pc_chain'}
    text = (capture/'observed.v').read_text()
    assert 'assume(!audit_rsp || audit_count != 0)' in text
    assert 'assert(!audit_cmd || audit_count < 8 || audit_rsp)' in text
    assert 'audit_fetch_pc[audit_tail]<=iBus_cmd_payload_pc' in text
    assert 'execute_arbitration_isFiring && audit_execute_live' in text
    assert 'CsrPlugin_jumpInterface_payload' in text
    result = generate(plan,capture,tmp_path/'jobs')
    assert len(result['rows']) == 4
    monitor = (tmp_path/'jobs/csr_consistency/monitor.sv').read_text()
    assert 'address == 832' in monitor  # Catalog address of mscratch.
    assert "32'd4294967295" in monitor
