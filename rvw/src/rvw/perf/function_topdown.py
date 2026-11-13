"""Time attribution of sampled commit slots to the next retiring function."""
from bisect import bisect_left, bisect_right
import hashlib
import json
from pathlib import Path
from rvw.probes.events import read
from rvw.probes.convert import _check_identity, _int, read_c2
from rvw.wave.symbols import Symbols
from .topdown import CLASSES, report


def attribute(stream, records, lookup, width=None):
    retirements = [r for r in records if not r.get('trap') and 'event' not in r]
    cycles = [int(r['cycle']) for r in retirements]
    if cycles != sorted(cycles):
        raise ValueError('C2 cycles must not decrease')
    rows = {}
    seen = set()
    for cycle, probe, values in stream.events('custom'):
        if probe.name != 'topdown_cycle':
            continue
        if cycle in seen:
            raise ValueError('duplicate topdown_cycle sample')
        seen.add(cycle)
        if set(values) != set(CLASSES) or any(v < 0 for v in values.values()):
            raise ValueError('topdown_cycle must have four nonnegative slot counts')
        if width is not None and sum(values.values()) != width:
            raise ValueError('sampled classes do not partition one cycle')
        i = bisect_left(cycles, cycle)
        name = lookup(_int(retirements[i]['pc'])) if i < len(cycles) else None
        row = rows.setdefault(name or '(unknown)', dict.fromkeys(CLASSES, 0))
        end = bisect_right(cycles, cycle)
        if values['retiring'] != end - i:
            raise ValueError('sampled retiring slots differ from C2 at this cycle')
        for record in retirements[i:end]:
            retired_name = lookup(_int(record['pc'])) or '(unknown)'
            rows.setdefault(retired_name, dict.fromkeys(CLASSES, 0))['retiring'] += 1
        for key in CLASSES[1:]:
            row[key] += values[key]
    if not seen:
        raise ValueError('per-function attribution needs topdown_cycle samples; totals are insufficient')
    return rows


def by_function(events, c2, elf, c1=None):
    if not c2:
        raise ValueError('per-function attribution needs C2')
    whole = report(events, c2, c1)
    stream = read(events)
    header, records, _ = read_c2(c2)
    _check_identity(stream, header)
    digest = hashlib.sha256(Path(elf).read_bytes()).hexdigest()
    if header.get('elf_sha256') != digest:
        raise ValueError('ELF hash differs from C2')
    symbols = Symbols(elf)
    def lookup(pc):
        hit = symbols.lookup(pc)
        return hit['symbol'] if hit else None
    rows = attribute(stream, records, lookup, width=whole["width"])
    for key in CLASSES:
        if sum(r[key] for r in rows.values()) != whole['slots'][key]:
            raise ValueError('sampled top-down counts differ from end totals')
    fractions = {name: {k: v / max(1, sum(row.values())) for k, v in row.items()} for name, row in rows.items()}
    whole.update(functions=rows, function_fractions=fractions, elf_sha256=digest,
                 attribution='retired slots use their C2 PC; lost slots use the next C2 retirement; trailing cycles unknown',
                 limits=['temporal attribution, not a causal stall diagnosis',
                         'lost-slot attribution cannot identify the instruction that caused a stall'])
    return whole


def compare(base, candidate):
    a, b = (json.loads(Path(p).read_text()) for p in (base, candidate))
    if any(r.get('schema') != 'rvw.topdown/1' for r in (a, b)):
        raise ValueError('expected two rvw.topdown/1 reports')
    if a.get('elf_sha256') != b.get('elf_sha256') or not a.get('elf_sha256'):
        raise ValueError('top-down comparison needs the same ELF hash')
    if a['slots']['retiring'] != b['slots']['retiring']:
        raise ValueError('top-down comparison needs equal retirement counts')
    if a.get('attribution') != b.get('attribution'):
        raise ValueError('attribution methods differ')
    rows = {}
    for name in sorted(set(a.get('functions', {})) | set(b.get('functions', {}))):
        rows[name] = {key: b.get('functions', {}).get(name, {}).get(key, 0)
                      - a.get('functions', {}).get(name, {}).get(key, 0) for key in CLASSES}
    return dict(schema='rvw.topdown-diff/1', status='reported', functions=rows,
                direction='candidate-minus-base', elf_sha256=a['elf_sha256'],
                base_identity=a.get('identity', {}), candidate_identity=b.get('identity', {}),
                cycles_delta=b['cycles']-a['cycles'], base_cycles=a['cycles'], candidate_cycles=b['cycles'],
                ipc_delta=b['slots']['retiring']/b['cycles']-a['slots']['retiring']/a['cycles'],
                slots_delta={key:b['slots'][key]-a['slots'][key] for key in CLASSES},
                limits=['absolute slot differences, not statistical significance or causal attribution'])
