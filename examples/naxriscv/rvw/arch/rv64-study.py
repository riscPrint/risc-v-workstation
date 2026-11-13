#!/usr/bin/env python3
"""Run existing consumers on captured RV64 benchmarks. Keep output outside Git."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, required=True)
    parser.add_argument('--elf-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    # This script lives in examples/naxriscv/rvw/arch in the workstation.
    root = Path(__file__).resolve().parents[4]
    project = root / 'examples/naxriscv'
    output = args.out.resolve()
    if output.is_relative_to(root):
        parser.error('--out must be outside the workstation checkout')
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for name in ('median', 'multiply', 'memcpy'):
        run = args.runs.resolve() / name
        elf = args.elf_dir.resolve() / (name + '.riscv')
        target = output / name
        target.mkdir()
        commands = {
            'probes': ['probes', 'check', '--events', str(run/'probe-events.jsonl'), '--validate', '--c2', str(run/'rvfi.jsonl')],
            'topdown': ['perf', 'topdown', str(run/'probe-events.jsonl'), '--c2', str(run/'rvfi.jsonl'), '--elf', str(elf), '--result', str(run/'result.json')],
            'model': ['ooo', str(project/'rvw/arch/ooo-resource.json'), str(run/'rvfi.jsonl'), '--max-cycles', '1000000'],
            'strict': ['cosim', 'check', '--elf', str(elf), '--trace', str(run/'rvfi.jsonl'), '--platform', str(project/'rvw/platform-rv64imasu.json'), '--strict'],
            'counter': ['cosim', 'check', '--elf', str(elf), '--trace', str(run/'rvfi.jsonl'), '--platform', str(project/'rvw/platform-rv64imasu.json'), '--strict-sync', 'mmio,csr,irq'],
        }
        reports = {}
        for key, command in commands.items():
            with (target/(key+'.json')).open('w') as out, (target/(key+'.log')).open('w') as log:
                result = subprocess.run(['nice', '-n', '10', sys.executable, '-m', 'rvw', '--project', str(project), *command, '--json'], cwd=root, stdout=out, stderr=log)
            report = json.loads((target/(key+'.json')).read_text())
            if result.returncode and not (key == 'strict' and report.get('status') == 'mismatch'):
                raise RuntimeError(f'{name}: {key} failed; see {target}')
            reports[key] = report
        c1 = json.loads((run/'result.json').read_text())
        checks = json.loads((run/'checks-run.json').read_text())
        if c1['config'] != 'rv64imasu' or c1['status'] != 'pass' or c1.get('inconclusive'):
            raise ValueError(f'{name}: need a conclusive rv64imasu pass')
        if reports['probes']['stream']['status'] != 'clean' or reports['topdown']['status'] != 'checked':
            raise ValueError(f'{name}: probes or topdown did not check cleanly')
        if reports['counter']['status'] != 'match' or reports['counter'].get('trace_complete') is not True:
            raise ValueError(f'{name}: counter-only comparison is not complete')
        if checks['inserted'] != 9 or checks['fired'] or not checks['capture']:
            raise ValueError(f'{name}: expected nine captured rules with zero firings')
        ipc = c1['instret'] / c1['cycles']
        model = reports['model']
        if model['instret'] != c1['instret']:
            raise ValueError(f'{name}: model retirement count differs from C1')
        rows.append(f"| {name} | {c1['cycles']:,} | {c1['instret']:,} | {ipc:.5f} | {model['cycles']:,} | {model['ipc']:.5f} | {(model['ipc']/ipc-1)*100:+.2f}% | {reports['counter']['synchronized']} |")
    print('| Program | RTL cycles | Retired | RTL IPC | Model cycles | Model IPC | IPC error | Counter synchronizations |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|')
    print('\n'.join(rows))
    print('Model config SHA256:', hashlib.sha256((project/'rvw/arch/ooo-resource.json').read_bytes()).hexdigest())
    print('Full consumer reports:', output)


if __name__ == '__main__':
    main()
