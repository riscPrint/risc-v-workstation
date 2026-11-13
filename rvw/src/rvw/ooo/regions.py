"""Model slot attribution by PC range. This is not hardware top-down analysis."""
from bisect import bisect_right
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

CATEGORIES = ('retiring', 'frontend_bound', 'bad_speculation',
              'backend_memory_bound', 'backend_core_bound')


class Regions:
    def __init__(self, width, ranges=()):
        self.width = width
        self.ranges = sorted(ranges)
        self.starts = [r[0] for r in self.ranges]
        for i, (lo, hi, name) in enumerate(self.ranges):
            if lo < 0 or hi <= lo or not name or (i and lo < self.ranges[i-1][1]):
                raise ValueError('regions must be named nonoverlapping half-open PC ranges')
        self.counts = defaultdict(Counter)

    def name(self, pc):
        if pc is None:
            return '<pipeline-empty>'
        i = bisect_right(self.starts, pc)-1
        return self.ranges[i][2] if i >= 0 and pc < self.ranges[i][1] else '<unmapped>'

    def observe(self, committed, rob, recovery, next_pc):
        for entry in committed:
            self.counts[self.name(entry.insn.pc)]['retiring'] += 1
        head = rob[0] if rob else None
        # Follow the oldest head's unfinished dependency chain to a memory op.
        def memory_blocked(entry, seen):
            if entry in seen:
                return False
            seen.add(entry)
            if entry.insn.kind in ('load', 'store'):
                return True
            return any(memory_blocked(d, seen) for d in entry.deps
                       if d.done is None or d.done > self.cycle)
        cause = ('bad_speculation' if recovery else
                 'backend_memory_bound' if head and (head.done is None or head.done > self.cycle) and memory_blocked(head, set()) else
                 'backend_core_bound' if head else 'frontend_bound')
        self.counts[self.name(head.insn.pc if head else next_pc)][cause] += self.width-len(committed)

    def report(self):
        totals = Counter()
        regions = {}
        for name, values in sorted(self.counts.items()):
            if not sum(values.values()):
                continue
            slots = {k: values[k] for k in CATEGORIES}
            regions[name] = dict(slots=slots, total_slots=sum(slots.values()),
                                 fractions={k:v/sum(slots.values()) for k,v in slots.items()})
            totals.update(slots)
        return dict(unit='commit_slots', slots={k: totals[k] for k in CATEGORIES},
                    total_slots=sum(totals.values()), regions=regions,
                    fractions={k:totals[k]/sum(totals.values()) for k in CATEGORIES},
                    method='retired PC; unused slots to oldest ROB PC or next unrenamed PC; memory includes unfinished head dependencies',
                    accuracy_status='inconclusive')


def elf_ranges(path):
    from rvw.runs.elf import Elf
    elf = Elf(str(path))
    # Keep sized symbols in executable sections. Aliases at one address share a range.
    symbols = {}
    for s in elf.symbols().values():
        if s.size and 0 < s.shndx < len(elf.sections) and elf.sections[s.shndx]['flags'] & 4:
            symbols.setdefault((s.value, s.value+s.size), []).append(s.name)
    return [(lo, hi, '|'.join(sorted(names))) for (lo, hi), names in symbols.items()]


def profile(config, trace, elf=None, regions=None, max_cycles=1000000):
    from .core import _instructions, simulate
    from .project import configuration
    cb, tb = Path(config).read_bytes(), Path(trace).read_bytes()
    description = json.loads(cb)
    c = configuration(description)
    if description.get('schema') == 'rvw.arch-core/1' and json.loads(tb.splitlines()[0])['config'] != description['config']:
        raise ValueError('project description does not match C2 selected config')
    ops = _instructions(tb, c.custom_instructions)
    if elf and regions:
        raise ValueError('select ELF symbols or explicit regions')
    ranges = elf_ranges(elf) if elf else ([(r['start'], r['end'], r['name'])
              for r in json.loads(Path(regions).read_text())] if regions else [])
    observer = Regions(c.commit_width, ranges)
    result = simulate(ops, c, max_cycles, backend='python', observer=observer)
    return dict(schema='rvw.ooo-profile/1', config_sha256=sha256(cb).hexdigest(),
                trace_sha256=sha256(tb).hexdigest(),
                region_sha256=sha256(Path(elf or regions).read_bytes()).hexdigest() if elf or regions else None,
                cycles=result['cycles'], instret=result['instret'], ipc=result['ipc'],
                attribution=observer.report(), model=result)


def compare(base, candidate):
    a, b = [json.loads(Path(p).read_text()) for p in (base, candidate)]
    if any(r.get('schema') != 'rvw.ooo-profile/1' for r in (a,b)):
        raise ValueError('expected OoO profiles')
    if a['trace_sha256'] != b['trace_sha256'] or a['region_sha256'] != b['region_sha256'] or a['instret'] != b['instret']:
        raise ValueError('profiles must use the same trace and region mapping')
    def delta(x, y):
        return {k: y.get(k, 0)-x.get(k, 0) for k in CATEGORIES}
    ar, br = a['attribution']['regions'], b['attribution']['regions']
    return dict(schema='rvw.ooo-profile-diff/1', cycles_saved=a['cycles']-b['cycles'],
                ipc_gain=b['ipc']-a['ipc'], speedup=a['cycles']/b['cycles'],
                slot_delta=delta(a['attribution']['slots'], b['attribution']['slots']),
                regions={k: delta(ar.get(k, {}).get('slots', {}), br.get(k, {}).get('slots', {}))
                         for k in sorted(ar.keys() | br.keys())},
                sign='candidate minus base; negative stall slots mean fewer stalls',
                accuracy_status='inconclusive')
