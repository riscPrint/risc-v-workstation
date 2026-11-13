#!/usr/bin/env python3
"""Alternating whole-core controls for settled-port snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
from rvw.common.proc import run_group

p = argparse.ArgumentParser(__doc__)
p.add_argument('--rtl', type=Path, required=True)
p.add_argument('--elf', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--repeats', type=int, default=4)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=False)
launcher = Path(__file__).resolve().parents[1] / 'engine-probe.py'
rows = []
expected = None
# One warm pair precedes alternating measured pairs.
for repeat in range(a.repeats + 1):
    for snapshot in ((False, True) if repeat % 2 == 0 else (True, False)):
        out = a.out / f'{repeat}-{int(snapshot)}'
        command = [sys.executable, str(launcher), '--backend', 'verilator', '--rtl', str(a.rtl),
                   '--elf', str(a.elf), '--out', str(out), '--seed', '7', '--max-cycles', '200000']
        if not snapshot:
            command.append('--no-port-snapshot')
        result = run_group(command, capture=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        report = json.loads((out / 'result.json').read_text())
        trace = (out / 'rvfi.jsonl').read_bytes()
        if expected is None:
            expected = trace
        if trace != expected or report['status'] != 'pass':
            raise RuntimeError('status or complete C2 differs')
        seconds = report['details']['execution_s']
        rows.append(dict(repeat=repeat, warmup=repeat == 0, snapshot=snapshot,
                         cycles=report['cycles'], instructions=report['instret'],
                         execution_s=seconds, cpu_s=report['details']['execution_cpu_s'],
                         cpu_instructions_per_s=report['instret']/report['details']['execution_cpu_s'], instructions_per_s=report['instret']/seconds,
                         trace_sha256=hashlib.sha256(trace).hexdigest()))
medians = {str(snapshot): statistics.median(r['instructions_per_s'] for r in rows
           if not r['warmup'] and r['snapshot'] == snapshot) for snapshot in (False, True)}
cpu_medians = {str(snapshot): statistics.median(r['cpu_instructions_per_s'] for r in rows
               if not r['warmup'] and r['snapshot'] == snapshot) for snapshot in (False, True)}
summary = dict(median_cpu_instructions_per_s=cpu_medians, snapshot_cpu_ratio=cpu_medians['True']/cpu_medians['False'], schema='rvw.native-port-speed/1', rows=rows, median_instructions_per_s=medians,
               snapshot_over_control=medians['True']/medians['False'],
               rtl_sha256=hashlib.sha256(a.rtl.read_bytes()).hexdigest(),
               elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
               scope='Verilator Python adapter execution plus C2 write/validation; compilation excluded')
(a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
