"""Multi-image inputs and independent checks at declared serialized boundaries."""
import hashlib
import json
from pathlib import Path
import re

from rvw.cosim.trace import Trace


def images(hart_images):
    """Build adapter input from HART=ELF arguments. No ELF is executed here."""
    rows = []
    for item in hart_images:
        hart, path = item.split('=', 1)
        if not re.fullmatch(r'0|[1-9][0-9]*', hart):
            raise ValueError('hart must be a nonnegative decimal integer')
        path = Path(path).resolve()
        data = path.read_bytes()
        if data[:4] != b'\x7fELF':
            raise ValueError(f'not an ELF: {path}')
        rows.append({'hart': int(hart), 'elf': str(path),
                     'elf_sha256': hashlib.sha256(data).hexdigest()})
    if len(rows) < 2 or len({r['hart'] for r in rows}) != len(rows):
        raise ValueError('at least two distinct hart images required')
    return {'schema': 'rvw.hart-images/1', 'harts': sorted(rows, key=lambda r: r['hart'])}


def decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r'0|[1-9][0-9]*', value):
        raise ValueError('serialization must be a canonical decimal string')
    return int(value)


def check(trace, reference):
    """Check captured bytes against stimulus, without ordering by retirement."""
    ref = json.loads(Path(reference).read_text())
    report = {'schema': 'rvw.memory-check/1', 'status': 'inconclusive',
              'checks': 0, 'scope': 'serialized boundary only', 'exhaustive_proof': False}
    reader = Trace(trace)
    try:
        if not reader.multihart:
            raise ValueError('C2/2 multi-hart trace required')
        records = list(reader)
        done = {r['hart']: r['status'] for r in records if r.get('event') == 'hart_end'}
        if set(done) != set(reader.header['harts']) or any(s != 'pass' for s in done.values()):
            return report | {'reason': 'all harts must complete with pass'}
        if ref.get('schema') != 'rvw.serialized-memory/1' or not ref.get('boundary'):
            raise ValueError('declared serialized-memory boundary required')
        memory, writers = {}, {}
        for region in ref['initial']:
            base, data = int(region['address'], 0), bytes.fromhex(region['bytes'])
            for offset, byte in enumerate(data):
                addr = base + offset
                if addr in memory:
                    raise ValueError('overlapping initial regions')
                memory[addr], writers[addr] = byte, 'initial'
        expected = ref['writes']
        used = set()
        events = [r for r in records if r.get('event') == 'external'
                  and r.get('boundary') == ref['boundary']]
        if not events:
            return report | {'reason': 'no accepted boundary events'}
        # Acceptance serialization can differ from both capture and retirement order.
        events.sort(key=lambda r: decimal(r['serialization']))
        for serial, event in enumerate(events):
            if decimal(event['serialization']) != serial:
                raise ValueError('memory serialization gap or duplicate')
            action = event['action']
            if action not in ('read', 'write'):
                return report | {'reason': f'unsupported boundary action: {action}'}
            address, data, mask = (int(event[k], 0) for k in ('address', 'data', 'mask'))
            if not 0 < mask < (1 << (reader.header['xlen'] // 8)):
                raise ValueError('byte mask must select XLEN byte lanes')
            indices = [i for i in range(reader.header['xlen'] // 8) if mask >> i & 1]
            if any(address + i not in memory for i in indices):
                raise ValueError('uncaptured initial memory bytes')
            if action == 'write':
                wanted = expected.get(event['id'])
                if wanted is None:
                    return report | {'reason': f'missing independent write: {event["id"]}'}
                if any(int(wanted[k], 0) != int(event[k], 0) for k in ('address', 'mask')):
                    return report | {'status': 'mismatch', 'reason': 'write address or mask differs from stimulus'}
                value = int(wanted['data'], 0)
                if any((value >> (8*i) & 255) != (data >> (8*i) & 255) for i in indices):
                    return report | {'status': 'mismatch', 'reason': 'write bytes differ from stimulus'}
                for i in indices:
                    memory[address+i], writers[address+i] = value >> (8*i) & 255, event['id']
                used.add(event['id'])
            else:
                if any(memory[address+i] != (data >> (8*i) & 255) for i in indices):
                    return report | {'status': 'mismatch', 'reason': 'read bytes differ from reference'}
                if event.get('read_from') != [writers[address+i] for i in indices]:
                    return report | {'status': 'mismatch', 'reason': 'read-from differs from reference'}
            report['checks'] += 1
        if used != set(expected):
            return report | {'reason': 'expected writes not observed'}
        return report | {'status': 'consistent'}
    finally:
        reader.close()
