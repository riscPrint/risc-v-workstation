"""Prepare pinned litmus programs for AtomicFixtureSpec, or compare its samples."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from litmus import PINS, canonical, compare


def reg(text):
    if not re.fullmatch(r'x(?:[0-9]|[12][0-9]|3[01])', text):
        raise ValueError('unsupported register')
    return int(text[1:])


def instruction(text):
    text = text.strip()
    if text == 'fence rw,rw':
        return 0x0330000f
    m = re.fullmatch(r'(lw|sw) (x\d+),0\((x\d+)\)', text)
    if not m:
        raise ValueError(f'unsupported fixture instruction: {text}')
    data, base = reg(m[2]), reg(m[3])
    return (base << 15) | (2 << 12) | ((data << 7) | 3 if m[1] == 'lw' else (data << 20) | 35)


def translate(text):
    """Strict translation of the four pinned tests, including initial registers."""
    match = re.search(r'\{([^}]+)\}\s*P0\s*\|\s*P1\s*;(.+?)exists', text, re.S)
    if not match:
        raise ValueError('unsupported litmus format')
    programs = [[], []]
    for entry in match[1].split(';'):
        if not entry.strip():
            continue
        m = re.fullmatch(r'\s*([01]):(x\d+)=(1|x|y)\s*', entry)
        if not m:
            raise ValueError('unsupported initial state')
        value = {'1': 1, 'x': 0, 'y': 4}[m[3]]
        programs[int(m[1])].append((value << 20) | (reg(m[2]) << 7) | 0x13)
    # Pad startup lengths. Initialization writes only private registers.
    length = max(map(len, programs))
    for p in programs:
        p.extend([0x13] * (length - len(p)))
    for line in match[2].split(';'):
        if not line.strip():
            continue
        columns = line.strip().split('|')
        if len(columns) != 2:
            raise ValueError('expected two harts')
        for p, asm in zip(programs, columns):
            p.append(instruction(asm))
    return programs


def prepare(tests, reference, out):
    pins = json.loads(PINS.read_text())
    if reference['pins'] != pins or reference['dut'] != 'not_run':
        raise ValueError('expected fresh pinned reference-only report')
    rows = []
    for case in reference['cases']:
        path = tests / case['test']
        if hashlib.sha256(path.read_bytes()).hexdigest() != pins['cases'][case['test']]:
            raise ValueError('test bytes differ from pins')
        rows.append({'test': case['test'], 'programs': translate(path.read_text()),
                     'projection': sorted(case['allowed'][0])})
    if {r['test'] for r in rows} != set(pins['cases']):
        raise ValueError('missing pinned case')
    out.write_text(json.dumps(rows, indent=2) + '\n')


def check(reference, samples):
    if {s['test'] for s in samples} != {r['test'] for r in reference['cases']} or len(samples) != len(reference['cases']):
        raise ValueError('missing or duplicate fixture case')
    rows = []
    for case in reference['cases']:
        sample = next(s for s in samples if s['test'] == case['test'])
        allowed = {canonical(s) for s in case['allowed']}
        rows.append({'test': case['test'], **compare(allowed, sample)})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--tests', type=Path)
    p.add_argument('--samples', type=Path)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    reference = json.loads(args.reference.read_text())
    if args.samples:
        rows = check(reference, json.loads(args.samples.read_text()))
        args.out.write_text(json.dumps(rows, indent=2) + '\n')
        return 1 if any(r['status'] == 'mismatch' for r in rows) else 3 if any(r['status'] != 'consistent' for r in rows) else 0
    if not args.tests:
        p.error('--tests is required to prepare a plan')
    prepare(args.tests, reference, args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
