#!/usr/bin/env python3
"""Compare each complete native capture with Spike without synchronization."""
import argparse
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('run', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
home = Path(os.environ['RVW_HOME'])
results = []
for test in sorted((args.run / 'isa/default/tests').iterdir()):
    trace = test / 'rvfi.jsonl'
    result = json.loads((test / 'result.json').read_text())
    if not trace.is_file():
        results.append(dict(test=test.name, status='error', message='missing C2'))
        continue
    completed = subprocess.run([
        'nice', '-n', '10', str(home / 'rvw/.venv/bin/rvw'),
        '--project', str(root), 'cosim', 'check',
        '--elf', str(root / 'rvw/out/isa' / test.name),
        '--trace', str(trace), '--strict', '--json',
    ], capture_output=True, text=True)
    report = json.loads(completed.stdout)
    mismatch = report.get('mismatch', {})
    row = dict(test=test.name, rtl_status=result['status'], status=report['status'],
               instructions=report.get('instructions'), synchronized=report.get('synchronized'),
               differences=mismatch.get('differences'), pc=mismatch.get('pc'),
               message=report.get('message'))
    results.append(row)
    print(json.dumps(row), flush=True)
output = args.run / 'strict-spike-summary.json'
output.write_text(json.dumps(results, indent=2) + '\n')
raise SystemExit(0 if all(row['status'] == 'match' for row in results) else 1)
