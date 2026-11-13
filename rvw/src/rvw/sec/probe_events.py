"""Probe events from the native harness, written as `rvw.probe-events/1`.

Two producers: SpinalProbes wires (`rvwprobe__KIND__NAME__FIELD`) found in the top module,
and project-declared `events` in the core binding that name internal signals. Each event
has a one-cycle `valid`. Counters are summed and written only in the end record.
"""
import json
from pathlib import Path
import re

WIRE = re.compile(r'\b(?:wire|reg)\s*(\[\s*(\d+)\s*:\s*0\s*\])?\s*(rvwprobe__([a-z]+)__(\w+?)__([a-z_]+))\s*;')
SAMPLED = ('branch', 'cache', 'tlb', 'walk', 'interrupt', 'csr', 'flush', 'retire', 'counter', 'custom')


def discover(binding, kinds=None):
    """Probe sites: list of {id, kind, name, valid, fields: [[field, width, signal]]}."""
    kinds = set(kinds or binding.get('probe_kinds', SAMPLED))
    text = '\n'.join(p.read_text() for p in binding['rtl'])
    top = re.search(r'\bmodule\s+'+re.escape(binding['top'])+r'\b.*?\bendmodule', text, re.S)
    sites = {}
    for width, msb, signal, kind, name, fieldname in WIRE.findall(top.group(0) if top else ''):
        if kind not in kinds or re.search(r'_\d+$', fieldname):
            continue  # skip kinds not sampled and Spinal's numbered duplicates
        site = sites.setdefault((kind, name), dict(kind=kind, name=name, valid=None, fields=[]))
        if fieldname == 'valid':
            site['valid'] = signal
        else:
            site['fields'].append([fieldname, int(msb)+1 if width else 1, signal])
    for e in binding.get('events', []):
        sites[(e['kind'], e['name'])] = dict(kind=e['kind'], name=e['name'], valid=e['valid'], meta=e.get('meta', {}),
                                             fields=[[f, int(w), s] for f, (s, w) in e['fields'].items()])
    # Elaboration metadata (for example branch `semantics`) is not in the Verilog; the binding gives it.
    for key, meta in binding.get('probe_meta', {}).items():
        if tuple(key.split(':', 1)) in sites:
            sites[tuple(key.split(':', 1))]['meta'] = meta
    found = [s for s in sites.values() if s['valid']]
    for i, s in enumerate(found):
        s['id'] = i
    return found


def testbench_lines(sites):
    lines = []
    for s in sites:
        values = ''.join(f', dut.{sig}' for _, _, sig in s['fields'])
        fmt = ' %0d' * len(s['fields'])
        lines.append(f'  if (dut.{s["valid"]}) $fdisplay(fd, "Q %0d {s["id"]}{fmt}", cycle{values});')
    return lines


def parse(text, sites):
    rows = []
    for line in text.splitlines():
        if line.startswith('Q '):
            w = [int(x) for x in line.split()[1:]]
            rows.append((w[0], w[1], w[2:]))
    return rows


def write(path, sites, rows, cycles, identity):
    """The stream file. Counter totals go in the end record."""
    counters = {}; counts = {}
    with open(path, 'w') as f:
        f.write(json.dumps(dict(schema='rvw.probe-events/1', identity=identity,
                                probes=[dict(id=s['id'], kind=s['kind'], name=s['name'],
                                             fields=[[n, w] for n, w, _ in s['fields']], meta=s.get('meta', {}))
                                        for s in sites]))+'\n')
        for cycle, i, values in rows:
            s = sites[i]
            counts[str(i)] = counts.get(str(i), 0)+1
            if s['kind'] == 'counter':
                inc = dict(zip([n for n, _, _ in s['fields']], values)).get('inc', 1)
                counters[s['name']] = counters.get(s['name'], 0)+inc
                continue
            f.write(json.dumps([cycle, i, *values])+'\n')
        f.write(json.dumps({'end': True, 'cycles': cycles, 'counters': counters, 'events': counts})+'\n')
    return counters


def collect(result):
    """Event dicts for observation channels: {cycle, kind, name, field: value...}."""
    sites = result.get('probe_sites', [])
    out = []
    for cycle, i, values in result.get('probe_rows', []):
        s = sites[i]
        out.append(dict(cycle=cycle, kind=s['kind'], name=s['name'],
                        **dict(zip([n for n, _, _ in s['fields']], values))))
    return out


def counters(result):
    totals = {}
    for e in collect(result):
        if e['kind'] == 'counter':
            totals[e['name']] = totals.get(e['name'], 0)+e.get('inc', 1)
    return totals
