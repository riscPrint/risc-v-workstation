"""Opt-in native controls for the instruction and concurrent IRQ fixtures."""
import json
import os
from pathlib import Path
import sys

import pytest
from rvw.common.proc import run_group
from rvw.cosim.trace import Trace
from rvw.reduce.streams import instruction_slots
from rvw.runs.elf import Elf

EXAMPLE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    rtl = os.environ.get('RVW_VEX_ENGINE_RTL')
    if not rtl or not os.environ.get('VEXRISCV'):
        pytest.skip('captured RTL and private VexRiscv source must be selected')
    root = tmp_path_factory.mktemp('reduction') / 'prepared'
    result = run_group([sys.executable, str(EXAMPLE / 'reduction/prepare.py'),
        '--rtl', rtl, '--out', str(root)], timeout=30, capture=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return root


def native(root, elf, name, schedule=None):
    out = root / name
    out.mkdir()  # Debug tools create the output directory before invoking the adapter.
    argv = [str(root / 'harness/run.sh'), 'run', '--elf', str(elf), '--out', str(out)]
    if schedule is not None:
        argv += ['--irq-schedule', schedule]
    result = run_group(argv, timeout=60, capture=True)
    assert result.returncode in (0, 1), result.stdout + result.stderr
    data = json.loads((out / 'result.json').read_text())
    checked = Trace(out / data['artifacts']['rvfi_trace'])
    try:
        records = list(checked)
    finally:
        checked.close()
    assert data['details']['c2_schema_validated']
    assert records[-1]['event'] == 'end' and records[-1]['status'] == data['status']
    assert (result.returncode == 0) == (data['status'] == 'pass')
    return data, records


def test_instruction_failure_has_a_passing_empty_control(prepared):
    elf = Elf(str(prepared / 'instructions.elf'))
    slots = instruction_slots(elf, 'fault_region')
    assert len(slots) == 8 and all(size == 4 for _, size in slots)
    failed, _ = native(prepared, prepared / 'instructions.elf', 'instruction-fail')
    assert failed['status'] == 'fail' and failed['fail_code'] == 1
    for offset, size in slots:
        elf.data[offset:offset + size] = bytes.fromhex('13000000')
    empty = prepared / 'empty.elf'
    elf.save(str(empty))
    passed, _ = native(prepared, empty, 'instruction-empty')
    assert passed['status'] == 'pass'
    assert empty.stat().st_size == (prepared / 'instructions.elf').stat().st_size


def test_concurrent_irq_failure_has_a_passing_quiet_control(prepared):
    failed, records = native(prepared, prepared / 'interrupts.elf', 'irq-fail',
                             '1:0x0,80:0x8')
    assert failed['status'] == 'fail' and failed['fail_code'] == 1
    assert any(row.get('event') == 'irq' and row['levels'] == 8 for row in records)
    assert any(row.get('event') == 'trap' and row['intr'] and row['cause'] == 0x80000003
               for row in records)
    passed, records = native(prepared, prepared / 'interrupts.elf', 'irq-quiet', '1:0x0')
    assert passed['status'] == 'pass'
    assert not any(row.get('event') == 'trap' for row in records)


@pytest.mark.parametrize('schedule', ['1:0x2', '2:0x8', '1:0x0,80:0x8,80:0x0'])
def test_invalid_or_absent_irq_input_cannot_publish_c1(prepared, schedule, tmp_path):
    out = tmp_path / 'rejected'
    result = run_group([str(prepared / 'harness/run.sh'), 'run', '--elf',
        str(prepared / 'interrupts.elf'), '--out', str(out), '--irq-schedule', schedule],
        timeout=10, capture=True)
    assert result.returncode == 3, result.stdout + result.stderr
    assert not (out / 'result.json').exists()
    assert not (out / 'native-run/native').exists()
