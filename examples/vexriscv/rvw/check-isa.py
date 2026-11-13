#!/usr/bin/env python3
"""Compare every ISA run in a native run-many manifest through rvw cosim."""
import argparse
import json
from pathlib import Path
import sys

from rvw.common.proc import run_group


def compare(manifest, output, *, core="vexriscv", platform=None):
    platform = Path(platform) if platform else Path(__file__).with_name('platform.json')
    rows = []
    for line in Path(manifest).read_text().splitlines():
        job = json.loads(line)
        command = [sys.executable, '-m', 'rvw', 'cosim', 'check', '--core', core,
                   '--platform', str(platform), '--elf', job['elf'],
                   '--trace', str(Path(job['out']) / 'rvfi.jsonl'), '--json']
        result = run_group(command, capture=True, text=True, timeout=60)
        report = json.loads(result.stdout) if result.stdout else dict(status='error', message=result.stderr)
        rows.append(dict(test=Path(job['elf']).name, exit_code=result.returncode, report=report))
        print(rows[-1]['test'], report['status'], flush=True)
    counts = {s: sum(r['report']['status'] == s for r in rows)
              for s in sorted({r['report']['status'] for r in rows})}
    Path(output).write_text(json.dumps(dict(counts=counts, runs=rows), indent=2) + '\n')
    print(json.dumps(counts))
    return 0 if rows and all(r['exit_code'] == 0 and r['report']['status'] == 'match'
                             and r['report'].get('trace_complete') for r in rows) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument("--core", default="vexriscv")
    parser.add_argument("--platform", type=Path)
    args = parser.parse_args()
    sys.exit(compare(args.manifest, args.output, core=args.core, platform=args.platform))
