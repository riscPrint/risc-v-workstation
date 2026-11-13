#!/usr/bin/env python3
"""Check every standalone observation, including the serial byte oracles."""
import argparse
import json
from pathlib import Path


def check(manifest, log):
    jobs = [line.split('\t')[4] for line in Path(manifest).read_text().splitlines() if line]
    rows = [json.loads(line.split('SOC_RESULT ',1)[1]) for line in Path(log).read_text().splitlines() if 'SOC_RESULT ' in line]
    if not jobs or len(rows) != len(jobs):
        raise ValueError('missing or extra native observations')
    failures=[]
    for name,row in zip(jobs,rows):
        expected = {'hello':'hello\n','uart_irq':'I'}.get(name)
        uart = bytes.fromhex(row['uart_hex']).decode('utf-8')
        if row['status']!='pass' or (expected is not None and uart!=expected):
            failures.append(dict(name=name,observation=row))
    return dict(status='fail' if failures else 'pass',programs=len(jobs),failures=failures,
                evidence='standalone simulation; not a C1 or gate result')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('log');a=p.parse_args()
    result=check(a.manifest,a.log);print(json.dumps(result,indent=2));raise SystemExit(result['status']!='pass')
