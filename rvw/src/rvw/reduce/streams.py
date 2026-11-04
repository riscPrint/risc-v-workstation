"""Order-preserving reduction inputs. Each removal requires a fresh oracle run."""
from __future__ import annotations

import re
from ..runs.elf import Elf


def minimize(items, probe):
    """ddmin by chunk removal. Return kept IDs and an honest completion reason.

    probe returns True (reproduced), False (conclusive non-match), or None
    (inconclusive). Never use an inconclusive result to prove local minimality.
    """
    kept = list(items)
    verdict = probe(kept)
    if verdict is not True:
        return kept, 'initial_not_reproduced' if verdict is False else 'inconclusive_or_budget'
    n = 2
    while kept:
        width = max(1, (len(kept) + n - 1) // n)
        for start in range(0, len(kept), width):
            candidate = kept[:start] + kept[start + width:]
            verdict = probe(candidate)
            if verdict is None:
                return kept, 'inconclusive_or_budget'
            if verdict:
                kept = candidate
                n = max(2, n - 1)
                break
        else:
            if width == 1:
                return kept, 'one_minimal'
            n = min(len(kept), n * 2)
            continue
    return kept, 'one_minimal'


def instruction_slots(elf: Elf, name: str):
    """One sized executable ELF symbol. Preserve addresses with 16/32-bit NOPs."""
    if int.from_bytes(elf.data[18:20], "little") != 243:
        raise ValueError("instruction reduction needs a RISC-V ELF")
    sym = elf.symbols().get(name)
    if sym is None or sym.size <= 0:
        raise ValueError(f'{name}: need a nonempty sized code symbol')
    if not 0 < sym.shndx < len(elf.sections):
        raise ValueError(f'{name}: invalid section')
    sec = elf.sections[sym.shndx]
    if not sec['flags'] & 4 or not sec['addr'] <= sym.value < sym.value + sym.size <= sec['addr'] + sec['size']:
        raise ValueError(f'{name}: symbol must fit in one executable section')
    off = elf.file_offset(sym.value)
    if off is None or elf.file_offset(sym.value + sym.size - 1) != off + sym.size - 1 or sym.value % 2:
        raise ValueError(f'{name}: symbol must be aligned and file-backed')
    slots, end = [], off + sym.size
    while off < end:
        half = int.from_bytes(elf.data[off:off+2], 'little')
        size = 2 if half & 3 != 3 else 4
        if size == 4 and half & 31 == 31 or off + size > end:
            raise ValueError(f'{name}: unsupported or truncated instruction')
        slots.append((off, size))
        off += size
    return slots


def irq_entries(text):
    entries = text.split(',')
    last = 0
    for item in entries:
        if not re.fullmatch(r'[0-9]+:0x[0-9a-fA-F]+', item):
            raise ValueError('irq schedule needs CYCLE:0xLEVELS pairs')
        cycle, level = item.split(':')
        cycle = int(cycle)
        if cycle <= last or last == 0 and cycle != 1 or int(level, 16) >= 1 << 64:
            raise ValueError('irq schedule must start at 1 with increasing cycles and 64-bit levels')
        last = cycle
    return entries


class Stimulus:
    """Project-owned events. The adapter must implement --stimulus-file."""
    def __init__(self, data):
        if (not isinstance(data, dict) or set(data) != {'schema', 'events'}
                or data['schema'] != 'rvw.stimulus/1' or not isinstance(data['events'], list)):
            raise ValueError('expected rvw.stimulus/1 events')
        self.data = data
        self.groups = {}
        seen = set()
        for event in data['events']:
            if (not isinstance(event, dict) or set(event) != {'id', 'kind', 'hart', 'after', 'group', 'required', 'payload'}
                    or any(not isinstance(event[k], str) or not event[k] for k in ('id', 'group'))
                    or event['id'] in seen or event['kind'] not in ('instruction', 'irq', 'transaction', 'device')
                    or type(event['hart']) is not int or event['hart'] < 0
                    or type(event['required']) is not bool or not isinstance(event['payload'], dict)
                    or not isinstance(event['after'], list)
                    or any(not isinstance(x, str) or x not in seen for x in event['after'])
                    or len(set(event['after'])) != len(event['after'])):
                raise ValueError('invalid stimulus event or forward dependency')
            seen.add(event['id'])
            self.groups.setdefault(event['group'], []).append(event)

    def candidate(self, kept):
        groups = set(kept)
        events = [e for e in self.data['events'] if e['group'] in groups]
        ids = {e['id'] for e in events}
        if any(e['required'] and e['id'] not in ids for e in self.data['events']):
            return None
        if any(set(e['after']) - ids for e in events):
            return None
        return dict(schema='rvw.stimulus/1', events=events)
