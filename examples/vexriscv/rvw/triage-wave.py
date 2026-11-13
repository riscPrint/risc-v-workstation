#!/usr/bin/env python3
"""Extract pre-edge samples at the first firing of each check from a VCD."""
import argparse
import hashlib
import json
from pathlib import Path


def extract(inventory, run, wave, controls):
    checks = {c['id']: c for c in inventory['checks']}
    firings = {c['id']: c for c in run['firings']}
    names, values, samples, rows = {}, {}, [], {}
    scope = []
    clock = None
    batch = []
    timestamp = 0

    def sample():
        nonlocal values
        old = dict(values)
        values.update(batch)
        if clock is None or old.get(clock) != '0' or values.get(clock) != '1':
            return
        # The monitors sample values before the edge, before register updates.
        samples.append((timestamp, old))
        for key, firing in firings.items():
            if key in rows or old.get(names.get(firing['fail_signal'])) != '1':
                continue
            c = checks[key]
            watched = list(dict.fromkeys([*c['signals'].get('valid', []),
                       *c['signals'].get('ready', []), *c['signals'].get('cancel', []), *controls]))
            rows[key] = dict(id=key, count=firing['count'], source=c['source'], detail=c['detail'],
                samples=[dict(time_ps=t, signals={n: v.get(names.get(n), 'absent') for n in watched})
                         for t, v in samples[-2:]])
        del samples[:-2]

    with wave.open() as stream:
        for line in stream:
            fields = line.split()
            if not fields:
                continue
            if fields[0] == '$scope': scope.append(fields[2])
            elif fields[0] == '$upscope': scope.pop()
            elif fields[0] == '$var':
                if scope == ['TOP', inventory['toplevel']]: names[fields[4]] = fields[3]
            elif fields[0] == '$enddefinitions': clock = names.get('clk')
            elif line.startswith('#'):
                sample(); batch = []; timestamp = int(line[1:])
            elif line[0] in '01xz': batch.append((line[1:].strip(), line[0]))
            elif line[0] in 'bB': batch.append((fields[1], fields[0][1:]))
        sample()
    if clock is None:
        raise ValueError('expected clk in the top-level VCD scope')
    return dict(schema='rvw.check-wave-triage/1', wave_sha256=hashlib.sha256(wave.read_bytes()).hexdigest(),
                checks=list(rows.values()), missing=sorted(set(firings)-rows.keys()),
                limits=['Samples show observed conditions, not design intent.',
                        'Binary values; absent means the signal is not present in this wave.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--wave', type=Path, required=True)
    parser.add_argument('--control', action='append', default=[])
    args = parser.parse_args()
    result = extract(json.loads(args.inventory.read_text()), json.loads(args.run.read_text()),
                     args.wave, args.control)
    print(json.dumps(result, indent=2))
    return 1 if result['missing'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
