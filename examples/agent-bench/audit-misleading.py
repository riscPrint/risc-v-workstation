#!/usr/bin/env python3
"""Replay misleading evidence cases from a real native C1/C2 capture."""
import argparse
import json
from pathlib import Path
import shutil
from rvw.agent_bench.audit import audit_run

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--run-dir', type=Path, required=True)
p.add_argument('--elf', type=Path, required=True)
p.add_argument('--wrong-elf', type=Path, required=True)
p.add_argument('--stale-rtl', required=True, help='Intended task RTL hash, different from this capture')
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=False)
rows = []
for case in ('control', 'stale-rtl', 'wrong-elf', 'unsupported-fields', 'missing-coverage', 'missing-end'):
    out = a.out / case
    out.mkdir()
    for name in ('result.json', 'rvfi.jsonl'):
        shutil.copy2(a.run_dir / name, out / name)
    expected = {'rtl_sha256': json.loads((a.run_dir / 'result.json').read_text())['rtl_sha256']}
    options = {}
    if case == 'stale-rtl':
        if a.stale_rtl == expected['rtl_sha256']:
            raise ValueError('stale case needs a different intended RTL identity')
        expected['rtl_sha256'] = a.stale_rtl
    if case == 'unsupported-fields':
        lines = (out / 'rvfi.jsonl').read_text().splitlines()
        head = json.loads(lines[0])
        head['capabilities'] = [*head.get('capabilities', ['state']), 'unsupported']
        lines[0] = json.dumps(head)
        (out / 'rvfi.jsonl').write_text('\n'.join(lines) + '\n')
    if case == 'missing-end':
        lines = (out / 'rvfi.jsonl').read_text().splitlines()
        if json.loads(lines[-1]).get('event') != 'end':
            raise ValueError('input must have a complete native run end')
        (out / 'rvfi.jsonl').write_text('\n'.join(lines[:-1]) + '\n')
    if case == 'missing-coverage':
        options['required_artifacts'] = ['coverage.dat']
    result = audit_run(out, a.wrong_elf if case == 'wrong-elf' else a.elf,
                       expected_identity=expected, **options)
    rows.append({'case': case, **result})
    print(case, result['status'])
(a.out / 'audit.json').write_text(json.dumps(rows, indent=2) + '\n')
