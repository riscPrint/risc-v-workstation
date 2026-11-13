#!/usr/bin/env python3
"""Scan tracked bytes and local Git metadata without printing secret values."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def scan(root=ROOT, since='2026-11-13'):
    spec=importlib.util.spec_from_file_location('release_scan',ROOT/'rvw/tests/test_release_hygiene.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    tree=mod.scan_tracked_tree(root)
    metadata=mod.metadata_report(root)
    since_arg = since + 'T00:00:00Z' if len(since) == 10 else since
    names=subprocess.check_output(['git','-C',str(root),'log','--since='+since_arg,'--name-only','--format=','--diff-filter=ACMR'],text=True).splitlines()
    changed=sorted({name for name in names if name})
    personal=[row for row in tree if row.endswith(':personal_path')]
    today=[row for row in personal if row.rsplit(':',2)[0] in changed]
    return dict(schema='rvw.release-scan/1',since=since,tracked_findings=tree,
                changed_file_count=len(changed),changed_personal_paths=today,
                metadata_findings=metadata['findings'],
                identity_counts={key:len(metadata[key]) for key in ('authors','committers','taggers')},
                commit_count=metadata['commit_count'],tag_count=metadata['tag_count'],
                publication_approval='not inferred; owner decision required under #79',
                scope='Tracked working tree bytes and locally reachable Git metadata only. No remote cache, archive expansion or secret absence claim.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--since',default='2026-11-13');a=p.parse_args()
    result=scan(since=a.since);print(json.dumps(result,indent=2))
    return int(bool(result['tracked_findings'] or result['metadata_findings']))
if __name__=='__main__':raise SystemExit(main())
