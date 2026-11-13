#!/usr/bin/env python3
"""Alternating native engine comparison with full C2 equality."""
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
p.add_argument('--repeats', type=int, default=3)
a = p.parse_args()
if a.repeats < 1:
    raise SystemExit('repeats must be positive')
a.out.mkdir(parents=True, exist_ok=False)
launcher = Path(__file__).resolve().parents[1] / 'engine-probe.py'
rows = []
expected = None
for repeat in range(a.repeats):
    engines = ('arcilator', 'verilator') if repeat % 2 == 0 else ('verilator', 'arcilator')
    for engine in engines:
        out = a.out / f'{repeat}-{engine}'
        command = [sys.executable, str(launcher), '--backend', engine, '--rtl', str(a.rtl),
                   '--elf', str(a.elf), '--out', str(out), '--seed', '7', '--max-cycles', '200000']
        if repeat == 0:
            command.append('--wave')
        result = run_group(command, capture=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        report = json.loads((out / 'result.json').read_text())
        trace = (out / 'rvfi.jsonl').read_bytes()
        if expected is None:
            expected = trace
        if trace != expected or report['status'] != 'pass':
            raise RuntimeError('native status or complete C2 differs')
        rows.append(dict(repeat=repeat, engine=engine, wave=repeat == 0,
                         cycles=report['cycles'], instructions=report['instret'],
                         execution_s=report['details']['execution_s'],
                         build_s=report['details']['model_compile_s'],
                         instructions_per_s=report['instret']/report['details']['execution_s'],
                         trace_sha256=hashlib.sha256(trace).hexdigest()))
# Wave-enabled controls have extra capture cost. Compare untraced paired samples.
medians = {engine: statistics.median(r['instructions_per_s'] for r in rows
           if r['engine'] == engine and (not r['wave'] or a.repeats == 1))
           for engine in ('arcilator', 'verilator')}
summary = dict(schema='rvw.native-engine-comparison/1',
               rtl_sha256=hashlib.sha256(a.rtl.read_bytes()).hexdigest(),
               elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(), rows=rows,
               median_instructions_per_s=medians,
               arcilator_over_verilator=medians['arcilator']/medians['verilator'],
               scope='execution includes Python bus/RVFI handling and C2 write/validation; build measured separately; bounded workload only')
(a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
