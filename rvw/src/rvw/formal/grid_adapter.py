"""Generic artifact adapter for the existing farm SSH worker protocol.

The farm transport calls the payload field ELF. Here those bytes are JSON, and
results are formal reports. No simulation C1 record is fabricated.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from .deep_grid import grid


def identity():
    from . import deep_model, deep_grid, rtl_grid, portfolio, aiger_input
    from rvw.farm import executor, worker
    files = [Path(p.__file__) for p in (deep_model, deep_grid, rtl_grid, portfolio, aiger_input, executor, worker)] + [Path(__file__)]
    return {'schema': 'rvw.formal-grid-adapter/1',
            'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in files}}


def run_many(manifest, jobs):
    if jobs < 1:
        raise ValueError('jobs must be positive')
    requests = [json.loads(line) for line in Path(manifest).read_text().splitlines() if line.strip()]
    def solve(row):
        raw = Path(row['elf']).read_bytes()
        payload = json.loads(raw)
        solve_grid = grid
        if payload['model'].get('input_kind') == 'rtl':
            from .rtl_grid import local
            solve_grid = local
        report = solve_grid(payload['model'], row['out'], **payload['settings'])
        report['request_sha256'] = sha256(raw).hexdigest()
        (Path(row['out']) / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(solve, requests))
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    commands = p.add_subparsers(dest='action', required=True)
    commands.add_parser('identity')
    run = commands.add_parser('run-many')
    run.add_argument('--manifest', required=True)
    run.add_argument('--jobs', type=int, default=1)
    args = p.parse_args()
    if args.action == 'identity':
        print(json.dumps(identity()))
    else:
        raise SystemExit(run_many(args.manifest, args.jobs))
