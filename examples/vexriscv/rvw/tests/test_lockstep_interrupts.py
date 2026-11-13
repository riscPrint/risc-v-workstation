"""Native timer and software interrupt synchronization over DPI lockstep."""
import json
import os
import sys

import pytest
from rvw.common.proc import run_group
from test_adapter import compile_elf, EXAMPLE


@pytest.mark.parametrize('irq', [3, 7])
@pytest.mark.parametrize('initial_tval', [0, 7])
def test_interrupt_lockstep(tmp_path, irq, initial_tval):
    elf = compile_elf(tmp_path, f'irq-{irq}', f'''
  li t0, {initial_tval}
  csrw mtval, t0
  la t0, handler
  csrw mtvec, t0
  li t0, {1 << irq}
  csrw mie, t0
  csrsi mstatus, 8
wait_irq:
  j wait_irq
handler:
  csrr a0, mcause
  li a1, {0x80000000 | irq}
  bne a0, a1, fail
  csrw mie, zero
  la t0, resume
  csrw mepc, t0
  mret
resume:
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
fail:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
''')
    out = tmp_path / 'run'
    command = [sys.executable, '-m', 'rvw', 'cosim', 'live', '--lockstep',
               '--core', 'vexriscv', '--platform', str(EXAMPLE/'platform.json'),
               '--elf', str(elf), '--out', str(out), '--timeout', '600', '--json',
               '--simulator', str(EXAMPLE/'run.sh'), 'run', '--elf', '{elf}',
               '--out', '{out}', '--mem-latency', '0', '--seed', '1',
               '--irq-schedule', f'1:0x0,200:0x{1 << irq:x},220:0x0',
               '--rvfi-trace', '--json']
    env = dict(os.environ, RVW_COSIM_DPI='1')
    env.pop('RVW_COSIM_FAULT_ORDER', None)
    result = run_group(command, env=env, capture=True, text=True, timeout=630)
    (tmp_path/'cosim.json').write_text(result.stdout)
    report = json.loads(result.stdout)
    if initial_tval:
        assert result.returncode == 1, report
        assert report['status'] == 'mismatch'
        difference = report['mismatch']['differences']['tval']
        assert int(difference['expected'], 0) == 0
        assert int(difference['actual'], 0) == initial_tval
        return
    assert result.returncode == 0, report
    assert report['status'] == 'match' and report['trace_complete'], report
    rows = [json.loads(l) for l in (out/'rvfi.jsonl').read_text().splitlines()]
    traps = [r for r in rows if r.get('event') == 'trap' and r['intr']]
    assert len(traps) == 1 and int(traps[0]['cause'], 16) == 0x80000000 | irq
    assert any(r.get('intr') and 'order' in r for r in rows)
    assert any(r.get('event') == 'irq' and r['cycle'] == 220 and r['levels'] == '0x0' for r in rows)
    assert any(int(r.get('insn', '0'), 16) == 0x30200073 for r in rows)
