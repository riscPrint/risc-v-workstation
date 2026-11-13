#!/usr/bin/env python3
"""Run one fixed 306-program coverage batch after the documented suite builds."""
import json
import os
from pathlib import Path
import subprocess

project = Path(__file__).resolve().parent.parent
out = project / 'rvw/out'
rows = []
def add(elf, name, **options):
    rows.append(dict(elf=str(elf), out=str(out/'coverage-runs'/name), coverage=True,
                     **{'rvfi-trace': True, 'max-cycles': 200000, 'seed': 17}, **options))
for name in ('smoke', 'fence-selfmod', 'illegal'):
    add(out/'programs'/name, name)
isa = sorted((out/'isa').glob('rv32u*-p-*'))
pmp = sorted((out/'pmp').glob('pmp-*.elf'))
interrupts = [json.loads(line) for line in (out/'scheduled/jobs.jsonl').read_text().splitlines()]
assert len(isa) == 50 and len(pmp) == 242 and len(interrupts) == 9, 'build the complete prerequisite suites first'
for elf in isa+pmp:
    add(elf, elf.stem)
for row in interrupts:
    add(row['elf'], Path(row['elf']).stem, **{'irq-schedule': row['irq-schedule']})
add(out/'pmp/protection-speculative.elf', 'protection-speculative')
add(out/'programs/flush-chain', 'flush-chain')
assert all(Path(row['elf']).is_file() for row in rows)
manifest = out/'coverage-jobs.jsonl'
manifest.write_text(''.join(json.dumps(row)+'\n' for row in rows))
subprocess.run([str(project/'rvw/run.sh'), 'run-many', '--manifest', str(manifest),
                '--jobs', '4', '--wall-timeout', '115', '--json'], check=True)
