#!/usr/bin/env python3
"""Submit a native C1 manifest to the local queue in persistent serial shards.

Run with the installed workstation Python. Start at most three queue workers.
Each shard starts one adapter server and writes into its attempt directory.
"""
import argparse
import json
from pathlib import Path
import sys

from rvw.farm.service import Queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--adapter', required=True, help='JSON argument array; use absolute paths')
    parser.add_argument('--root', required=True)
    parser.add_argument('--owner', default='local')
    parser.add_argument('--shards', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    if not 1 <= args.shards <= 3:
        parser.error('use one to three serial shards on this shared machine')
    rows = [json.loads(line) for line in Path(args.manifest).read_text().splitlines() if line.strip()]
    adapter = json.loads(args.adapter)
    queue = Queue(args.root)
    submitted = []
    for index in range(min(args.shards, len(rows))):
        manifest = queue.root / f'manifest-{index}-{__import__("uuid").uuid4().hex}.jsonl'
        manifest.write_text(''.join(json.dumps(row)+'\n' for row in rows[index::args.shards]))
        submitted.append(queue.submit(args.owner, ['nice', '-n', '10', sys.executable,
            '-m', 'rvw.farm.native_shard', '--manifest', str(manifest), '--adapter', json.dumps(adapter),
            '--out', '{attempt_dir}', '--timeout', str(args.timeout)], retries=1, timeout=args.timeout+60)['id'])
    print(json.dumps(dict(jobs=submitted, workers='launch separately; at most three')))


if __name__ == '__main__':
    main()
