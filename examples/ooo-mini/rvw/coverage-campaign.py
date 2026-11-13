#!/usr/bin/env python3
"""Run a fixed coverage batch after the documented suite builds."""
import argparse
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--extended', action='store_true', help='Add the 72 M/U privilege cases and full-ROB IRQ schedule.')
args = parser.parse_args()
project = Path(__file__).resolve().parent.parent
out = project / 'rvw/out'
runs = out / ('coverage-device-runs' if args.extended else 'coverage-runs')
rows = []
def add(elf, name, **options):
    rows.append(dict(elf=str(elf), out=str(runs/name), coverage=True,
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
if args.extended:
    privilege = sorted((out/'disabled-mu32').glob('*.elf'))
    assert len(privilege) == 72, 'build the complete M/U privilege family first'
    for elf in privilege:
        add(elf, elf.stem)
    full = dict(next(row for row in rows if Path(row['elf']).stem == 'precise-3'))
    full['out'] = str(runs/'irq-full-3')
    full['irq-schedule'] = '1:0x0,32:0x8,20000:0x0'
    rows.append(full)
    for row in rows:
        row['probes'] = True
    assert len(rows) == 379
assert all(Path(row['elf']).is_file() for row in rows)
manifest = out/('coverage-device-jobs.jsonl' if args.extended else 'coverage-jobs.jsonl')
manifest.write_text(''.join(json.dumps(row)+'\n' for row in rows))
subprocess.run([str(project/'rvw/run.sh'), 'run-many', '--manifest', str(manifest),
                '--jobs', '4', '--wall-timeout', '115', '--json'], check=True)

if args.extended:
    import importlib.util
    spec = importlib.util.spec_from_file_location('project_probe_checks', project/'rvw/check-probes.py')
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    checks.out = out/'coverage-device-comparison'
    checks.out.mkdir(exist_ok=False)
    checks.compare(rows)
    checks.out = out
    checks.qualify(runs)
