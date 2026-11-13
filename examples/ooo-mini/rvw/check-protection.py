#!/usr/bin/env python3
"""Regenerate the default core's bounded PMP campaign and directed fault test."""
import json
import os
from pathlib import Path
import subprocess

home = Path(os.environ['RVW_HOME'])
project = Path(__file__).resolve().parent.parent
out = project / 'rvw/out/pmp'
rvw = str(home / 'rvw/.venv/bin/rvw')
subprocess.run([rvw, 'regress', 'privilege', 'build',
                str(home / 'examples/privilege/pmp-rv32.json'), '--out', str(out)], check=True)
subprocess.run(['nice', '-n', '10', os.environ.get('RISCV_GCC', 'riscv64-unknown-elf-gcc'),
                '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib', '-T', str(project / 'rvw/link.ld'),
                str(project / 'rvw/protection-speculative.S'), '-o', str(out / 'protection-speculative.elf')], check=True)
rows = [{'elf': str(elf), 'out': str(out.parent / 'pmp-runs' / elf.stem),
         'rvfi-trace': True, 'max-cycles': 30000, 'seed': 17} for elf in sorted(out.glob('*.elf'))]
manifest = out / 'jobs.jsonl'
manifest.write_text(''.join(json.dumps(row)+'\n' for row in rows))
subprocess.run([str(project / 'rvw/run.sh'), 'run-many', '--manifest', str(manifest),
                '--jobs', '4', '--wall-timeout', '115', '--json'], check=True)
# Capture the shared reference inputs once. Each fresh Spike instance runs the
# same strict checker as `rvw cosim check`; no register synchronization is enabled.
from rvw.common.capture import Capture
from rvw.cosim.spike import Spike, capture_shim
from rvw.cosim.platform import Platform
from rvw.cosim.checker import check
capture = Capture(out.parent / 'pmp-reference-inputs')
shim = capture_shim(capture, home / 'Cosim/build/librvw_spike.so')
platform = Platform.load('ooo-mini', capture.file(project / 'rvw/platform.json').copy)
for row in rows:
    model = Spike(platform, capture.file(Path(row['elf'])).copy, shim=shim)
    try:
        report = check(capture.file(Path(row['out']) / 'rvfi.jsonl').copy, model, platform, sync=())
    finally:
        model.close()
    print(json.dumps({'test': Path(row['elf']).stem, 'status': report['status'],
                      'instructions': report.get('instructions'), 'synchronized': report.get('synchronized')}), flush=True)
(capture.root / 'receipt.json').write_text(json.dumps(capture.record()))
