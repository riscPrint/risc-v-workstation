#!/usr/bin/env python3
"""Build and run the six generated machine interrupt cases on this core.

Run from the workstation checkout. Raw outputs stay in the ignored rvw/out tree.
"""
import json
import os
from pathlib import Path
import subprocess

home = Path(os.environ['RVW_HOME'])
project = Path(__file__).resolve().parent.parent
out = project / 'rvw/out/scheduled'
rvw = str(home / 'rvw/.venv/bin/rvw')
subprocess.run([rvw, 'regress', 'privilege', 'build',
                str(home / 'examples/privilege/scheduled-wfi-rv32.json'), '--out', str(out)], check=True)
for bit in (3, 7, 11):
    subprocess.run(['nice', '-n', '10', os.environ.get('RISCV_GCC', 'riscv64-unknown-elf-gcc'),
                    '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib', '-T', str(project / 'rvw/link.ld'),
                    f'-DIRQ_CAUSE={0x80000000 + bit}', str(project / 'rvw/interrupt-precise.S'),
                    '-o', str(out / f'precise-{bit}.elf')], check=True)
manifest = out / 'jobs.jsonl'
rows = []
for elf in sorted(out.glob('*.elf')):
    bit = int(elf.stem.split('-')[1 if elf.stem.startswith('precise-') else 2])
    rows.append({'elf': str(elf), 'out': str(out.parent / 'irq-runs' / elf.stem),
                 'irq-schedule': f'1:0x0,1000:{hex(1 << bit)},20000:0x0',
                 'rvfi-trace': True, 'max-cycles': 30000, 'seed': 17})
manifest.write_text(''.join(json.dumps(row) + '\n' for row in rows))
subprocess.run([str(project / 'rvw/run.sh'), 'run-many', '--manifest', str(manifest),
                '--jobs', '1', '--wall-timeout', '115', '--json'], check=True)
for row in rows:
    command = [rvw, '--project', str(project), 'cosim', 'check', '--elf', row['elf'],
               '--trace', str(Path(row['out']) / 'rvfi.jsonl'), '--strict', '--json']
    completed = subprocess.run(command, capture_output=True, text=True)
    report = json.loads(completed.stdout)
    print(json.dumps({'test': Path(row['elf']).stem, 'comparison': 'strict',
                      'status': report['status'], 'instructions': report.get('instructions'),
                      'synchronized': report.get('synchronized')}), flush=True)
    if Path(row['elf']).stem.endswith('-0'):
        command[command.index('--strict')] = '--strict-sync'
        command.insert(command.index('--strict-sync')+1, 'counter,mmio,csr')
        completed = subprocess.run(command, capture_output=True, text=True)
        report = json.loads(completed.stdout)
        print(json.dumps({'test': Path(row['elf']).stem, 'comparison': 'irq synchronization only',
                          'status': report['status'], 'instructions': report.get('instructions'),
                          'synchronized': report.get('synchronized')}), flush=True)
