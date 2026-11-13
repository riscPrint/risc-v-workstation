#!/usr/bin/env python3
"""Measure native adapter execution time with and without DPI comparison."""
import json
import os
from pathlib import Path
import sys

from rvw.common.proc import run_group

sys.path.insert(0, str(Path(__file__).with_name('tests')))
from test_adapter import compile_elf, EXAMPLE

out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
elf = compile_elf(out, 'loop', '''
  li t0, 2000
  li a0, 0
loop:
  addi a0, a0, 1
  addi t0, t0, -1
  bnez t0, loop
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
''')
env = dict(os.environ, RVW_COSIM_DPI='1')
env.pop('RVW_COSIM_FAULT_ORDER', None)
rows = []
# Warm both paths, then alternate baseline and checked trials.
for index, checked in enumerate((False, True, False, True, False, True)):
    run = out / str(index)
    adapter = [str(EXAMPLE/'run.sh'), 'run', '--elf', str(elf), '--out', str(run),
               '--mem-latency', '0', '--seed', '1', '--rvfi-trace', '--json']
    if checked:
        adapter = ['{elf}' if part == str(elf) else '{out}' if part == str(run) else part
                   for part in adapter]
        command = [sys.executable, '-m', 'rvw', 'cosim', 'live', '--lockstep',
                   '--core', 'vexriscv', '--platform', str(EXAMPLE/'platform.json'),
                   '--elf', str(elf), '--out', str(run), '--timeout', '600', '--json',
                   '--simulator', *adapter]
    else:
        command = adapter
    result = run_group(command, env=env, timeout=630, capture=True, text=True)
    (out/f'{index}.log').write_text(result.stderr + result.stdout)
    assert result.returncode == 0, (out/f'{index}.log')
    if checked:
        comparison = json.loads(result.stdout)
        assert comparison['status'] == 'match' and comparison['trace_complete'], comparison
    c1 = json.loads((run/'result.json').read_text())
    assert c1['status'] == 'pass', c1
    rows.append(dict(checked=checked, warmup=index < 2, cycles=c1['cycles'],
                     instret=c1['instret'], execution_s=c1['details']['execution_s']))
    (out/'measurements.json').write_text(json.dumps(rows, indent=2)+'\n')
    print(rows[-1], flush=True)
