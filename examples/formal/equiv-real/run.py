#!/usr/bin/env python3
"""Run both prepared cases through the public one-command revision flow."""
import argparse
import json
from pathlib import Path
import subprocess


def run(cases, out, timeout=180):
    entries = json.loads(Path(cases).read_text())
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    executable = Path(__file__).resolve().parents[3] / 'rvw/.venv/bin/rvw'
    records = []
    for name, case in entries.items():
        proof = out / name
        command = ['nice', '-n', '10', str(executable), '--project', case['project'],
                   'formal', 'equiv', '--gold-rev', case['gold'], '--gate-rev', case['gate'],
                   '--top', case['top'], '--reset', 'reset', '--settle', '12',
                   '--unmatched-state', 'prove', '--timeout', str(timeout), '--out', str(proof), '--json']
        result = subprocess.run(command, capture_output=True, text=True)
        (out/(name+'.log')).write_text(result.stdout+result.stderr)
        report = json.loads((proof/'result.json').read_text()) if (proof/'result.json').exists() else {}
        records.append({'case':name, 'command':command, 'exit':result.returncode,
                        'status':report.get('status','inconclusive'), 'reason':report.get('reason'),
                        'wall_s':report.get('wall_s')})
        (out/'summary.json').write_text(json.dumps(records,indent=2)+'\n')
    return records


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--cases',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--timeout',type=float,default=180)
    a = p.parse_args()
    print(json.dumps(run(a.cases,a.out,a.timeout),indent=2))
