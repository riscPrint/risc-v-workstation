#!/usr/bin/env python3
"""Relocate a measured local shard plan, render Jobs, and validate offline.

This copies manifests, not ELF bytes. Stage the hashed inputs on the PVC before
cluster execution. Supply each path replacement explicitly. No kubectl runs.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from rvw.farm.batch import render
from rvw.farm.k8s_validate import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--openapi', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--replace', action='append', default=[], metavar='OLD=NEW')
    args = parser.parse_args()
    replacements = sorted((s.split('=', 1) for s in args.replace), key=lambda pair: -len(pair[0]))
    def move(value):
        if isinstance(value, str):
            for old, new in replacements:
                value = value.replace(old, new)
            return value
        if isinstance(value, list):
            return [move(v) for v in value]
        if isinstance(value, dict):
            return {k: move(v) for k, v in value.items()}
        return value
    source = Path(args.plan)
    plan = move(json.loads(source.read_text()))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    for manifest in source.parent.glob('shard-*.jsonl'):
        (out / manifest.name).write_text(''.join(json.dumps(move(json.loads(line)))+'\n'
            for line in manifest.read_text().splitlines() if line.strip()))
    jobs = render(plan)
    report = validate(jobs, args.openapi)
    negative = copy.deepcopy(jobs)
    del negative['items'][0]['spec']['template']['spec']['containers']
    report['missing_containers_control'] = validate(negative, args.openapi)
    report['local_plan_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    for name, value in [('plan.json', plan), ('jobs.json', jobs), ('validation.json', report)]:
        (out / name).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if report['status'] == 'valid' and report['missing_containers_control']['status'] == 'invalid' else 1


if __name__ == '__main__':
    raise SystemExit(main())
