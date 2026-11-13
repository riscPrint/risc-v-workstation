#!/usr/bin/env python3
"""Replay the saved candidates against an exact captured VexTop export."""
import argparse
import hashlib
import json
from pathlib import Path
from rvw.common.proc import run_group


def check_log(text):
    if 'RVW_DONE' not in text or 'RVW_X ' in text:
        return False
    samples = [line for line in text.splitlines() if line.startswith('RVW_SAMPLE') and 'reset=0' in line]
    return bool(samples) and all('ibus=x' not in line and 'dbus=x' not in line
                                 and 'ibus=z' not in line and 'dbus=z' not in line for line in samples)


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--rtl', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    here = Path(__file__).resolve().parent
    expected = json.loads((here / 'results.json').read_text())['rtl_sha256']
    if hashlib.sha256(a.rtl.read_bytes()).hexdigest() != expected:
        p.error('RTL differs from the captured candidate export; regenerate candidates first')
    a.out.mkdir(parents=True, exist_ok=False)
    for i in range(2):
        exe = a.out / f'trace{i}.vvp'
        r = run_group(['nice', '-n', '10', 'iverilog', '-g2012', '-DSYNTHESIS', '-s', 'replay_top',
                       '-o', str(exe), str(a.rtl), str(here / f'trace{i}.sv')], timeout=30, capture=True)
        if r.returncode: return 3
        r = run_group(['nice', '-n', '10', 'vvp', str(exe)], timeout=30, capture=True)
        (a.out / f'trace{i}.log').write_text((r.stdout or '') + (r.stderr or ''))
        if r.returncode or not check_log(r.stdout or ''): return 1
    print('Both saved X witnesses are rejected by source four-state replay from reset.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
