"""Native DPI retirement checking and an explicit adapter writeback fault."""
import json
import os
from pathlib import Path
import sys

from rvw.common.proc import run_group
from test_adapter import EXAMPLE, compile_elf


def test_dpi_match_and_fault(tmp_path):
    elf = compile_elf(tmp_path, 'dpi', '''
  li a0, 7
  addi a1, a0, 2
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
''')
    for fault in (False, True):
        out = tmp_path / ('fault' if fault else 'clean')
        env = dict(os.environ, RVW_COSIM_DPI='1')
        if fault:
            env['RVW_COSIM_FAULT_ORDER'] = '1'
        else:
            env.pop('RVW_COSIM_FAULT_ORDER', None)
        command = [sys.executable, '-m', 'rvw', 'cosim', 'live', '--lockstep',
                   '--core', 'vexriscv', '--platform', str(EXAMPLE/'platform.json'),
                   '--elf', str(elf), '--out', str(out), '--timeout', '600', '--json',
                   '--simulator', str(EXAMPLE/'run.sh'), 'run', '--elf', '{elf}',
                   '--out', '{out}', '--mem-latency', '0', '--rvfi-trace', '--json']
        result = run_group(command, env=env, timeout=630, capture=True, text=True)
        (tmp_path / (out.name + "-cosim.json")).write_text(result.stdout)
        report = json.loads(result.stdout)
        if fault:
            assert result.returncode == 1, report
            assert report['status'] == 'mismatch'
            assert report['mismatch']['order'] == 1
            assert 'rd_wdata' in report['mismatch']['differences']
            rows = [json.loads(l) for l in (out/'rvfi.jsonl').read_text().splitlines()]
            assert [r['order'] for r in rows if 'order' in r] == [0, 1]
        else:
            assert result.returncode == 0, report
            assert report['status'] == 'match' and report['trace_complete']
