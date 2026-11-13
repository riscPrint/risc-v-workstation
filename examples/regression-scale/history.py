#!/usr/bin/env python3
"""Copy recorded queue jobs into one dashboard history without re-execution."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
from rvw.farm.service import Queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--skip-active', action='store_true')
    parser.add_argument('--job', action='append', default=[], help='copy only these recorded job IDs')
    parser.add_argument('queues', nargs='+')
    args = parser.parse_args()
    destination = Queue(args.out)
    imported, skipped = [], []
    for source_path in args.queues:
        source = Queue(source_path)
        for original in source.jobs():
            if args.job and original['id'] not in args.job:
                continue
            if original['state'] in ('running', 'cancel_requested', 'queued'):
                if args.skip_active:
                    skipped.append(original['id'])
                    continue
                raise ValueError('import only terminal queue records')
            job = deepcopy(original)
            old = source.root/job['id']
            target = destination.root/job['id']
            if target.exists():
                raise ValueError('job already imported')
            if old.exists():
                shutil.copytree(old, target)
            job['metadata']['history_import'] = dict(source=str(old), operation='copy; no execution',
                c3_sha256={str(p.relative_to(old)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in old.rglob('results.json')} if old.exists() else {})
            for attempt in job['attempts']:
                if attempt.get('directory'):
                    attempt['origin_directory'] = attempt['directory']
                    attempt['directory'] = str(target/Path(attempt['directory']).name)
            with destination.connect() as db:
                destination.save(db, job)
            imported.append(job['id'])
    print(json.dumps(dict(imported=imported, skipped_active=skipped, operation='copy; no execution')))


if __name__ == '__main__':
    main()
