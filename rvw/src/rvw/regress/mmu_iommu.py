"""Bounded IOMMU scenario model and device-side request agent.

Contexts are decoded project data, not raw DDT/PDT encodings. This model does
not replace the pinned architectural C reference for full conformance.
"""
from collections import deque
from copy import deepcopy

from .mmu import number

UPSTREAM = dict(url='https://github.com/riscv-non-isa/riscv-iommu',
                revision='ac1589c79d72ff109b8df6cb24803390c5021c4b',
                path='iommu_ref_model')


class Fault(Exception):
    def __init__(self, stage, status, address):
        self.stage, self.status, self.address = stage, status, address


class Model:
    def __init__(self, contexts, memory, queue_size=8):
        if queue_size < 2 or queue_size & (queue_size - 1):
            raise ValueError('queue_size must be a power of two at least two')
        self.contexts = deepcopy(contexts)
        self.memory = {number(k): number(v) for k, v in memory.items()}
        self.cache = {}
        self.faults, self.commands = deque(), deque()
        self.queue_size, self.overflow = queue_size, False
        self.fence_sequence = 0

    def _stage(self, context, address, access, stage, reader=None):
        if context.get('mode') == 'bare':
            return address
        from .mmu_walk import walk
        result = walk(mode=context['mode'], root=context['root'], va=address,
                      access=access, memory=self.memory,
                      privilege='U' if stage == 'second' else context.get('privilege', 'U'),
                      x4=stage == 'second', pte_reader=reader)
        if result['status'] != 'success':
            raise Fault(stage, result['status'], address)
        return result['pa']

    def translate(self, request):
        did, pid = request['device'], request.get('process')
        address = number(request['address'])
        access = request['access']
        if access not in ('load', 'store', 'fetch') or not 0 <= did < 1 << 24 or pid is not None and not 0 <= pid < 1 << 20:
            raise ValueError('invalid device request')
        size = request.get('size', 4)
        if size not in (1, 2, 4, 8) or address % 4096 + size > 4096:
            raise ValueError('request must fit one page and have a supported size')
        key = did, pid, access, address >> 12
        try:
            if did not in self.contexts or not self.contexts[did].get('valid', True):
                raise Fault('device', 'invalid-context', address)
            dc = self.contexts[did]
            if key in self.cache:
                return dict(status='translated', pa=self.cache[key] | (address & 4095), cached=True)
            first = dc.get('first', {'mode': 'bare'})
            if pid is not None:
                if pid not in dc.get('processes', {}):
                    raise Fault('process', 'invalid-context', address)
                first = dc['processes'][pid]
            second = dc.get('second', {'mode': 'bare'})
            def read_pte(gpa):
                hpa = self._stage(second, gpa, 'load', 'second')
                if hpa not in self.memory:
                    raise Fault('first', 'pte-access-fault', gpa)
                return self.memory[hpa]
            gpa = self._stage(first, address, access, 'first', read_pte)
            msi = dc.get('msi')
            if msi and access == 'store' and gpa & number(msi['mask']) == number(msi['pattern']):
                index = gpa >> 12
                if index not in msi['pages']:
                    raise Fault('msi', 'invalid-msi-entry', gpa)
                pa = number(msi['pages'][index]) | (gpa & 4095)
            else:
                pa = self._stage(second, gpa, access, 'second')
            self.cache[key] = pa & ~4095
            return dict(status='translated', pa=pa, cached=False)
        except Fault as fault:
            record = dict(device=did, process=pid, access=access, address=address,
                          stage=fault.stage, cause=fault.status, fault_address=fault.address)
            if len(self.faults) == self.queue_size - 1:
                self.overflow = True
            else:
                self.faults.append(record)
            return dict(status='fault', **record)

    def enqueue(self, command):
        if len(self.commands) == self.queue_size - 1:
            raise ValueError('command queue full')
        if command.get('op') not in ('iotinval', 'iodir', 'iofence'):
            raise ValueError('unsupported decoded IOMMU command')
        self.commands.append(dict(command))

    def process_command(self):
        if not self.commands:
            return None
        command = self.commands.popleft()
        if command['op'] == 'iofence':
            self.fence_sequence += 1
            return dict(status='completed', sequence=self.fence_sequence)
        for key in list(self.cache):
            did, pid, _, page = key
            if (command.get('device') is None or did == command['device']) and (command.get('process') is None or pid == command['process']) and (command.get('address') is None or page == number(command['address']) >> 12):
                del self.cache[key]
        return dict(status='completed')


def device_agent(model, requests, exchange):
    """Send the same decoded requests to a reference and a project device agent.

    exchange is the project transport. Responses must be independently captured.
    Missing responses remain inconclusive. Compare faults as well as addresses.
    """
    rows = []
    for sequence, request in enumerate(requests):
        expected = model.translate(request)
        observed = exchange(dict(request, sequence=sequence))
        status = 'inconclusive' if observed is None else 'match' if all(observed.get(k) == v for k, v in expected.items() if k != 'cached') else 'mismatch'
        rows.append(dict(sequence=sequence, status=status, expected=expected, observed=observed))
    return dict(status='mismatch' if any(r['status'] == 'mismatch' for r in rows) else 'consistent' if rows and all(r['status'] == 'match' for r in rows) else 'inconclusive', requests=rows)


def run(description, observations=None, result=None):
    """Run decoded scenario steps and compare optional independent agent output."""
    import hashlib
    import json
    from pathlib import Path
    path = Path(description)
    raw = json.loads(path.read_text())
    if raw.get('schema') != 'rvw.iommu-scenarios/1':
        raise ValueError('expected rvw.iommu-scenarios/1')
    contexts = {number(k): v for k, v in raw['contexts'].items()}
    for context in contexts.values():
        if 'processes' in context:
            context['processes'] = {number(k): v for k, v in context['processes'].items()}
        if 'msi' in context:
            context['msi']['pages'] = {number(k): v for k, v in context['msi']['pages'].items()}
    model = Model(contexts, raw.get('memory', {}), raw.get('queue_size', 8))
    capture = json.loads(Path(observations).read_text()) if observations else None
    if capture is not None and (not isinstance(capture, dict) or capture.get('schema') != 'rvw.iommu-observations/1' or not isinstance(capture.get('records'), list)):
        raise ValueError('expected rvw.iommu-observations/1 with records')
    observed = capture['records'] if capture else None
    description_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    bound = False
    if result and capture:
        from rvw.results.schema import load_run
        c1 = load_run(result)
        c1_path = c1.path / 'result.json'
        raw_c1 = json.loads(c1_path.read_text())
        identity = capture.get('identity', {})
        bound = (c1.status == 'pass' and not c1.why_inconclusive
                 and capture.get('c1_sha256') == hashlib.sha256(c1_path.read_bytes()).hexdigest()
                 and raw_c1.get('details', {}).get('iommu_description_sha256') == description_hash
                 and bool(identity.get('rtl_sha256'))
                 and all(k in identity and identity[k] == raw_c1.get(k) for k in ('core', 'config', 'elf_sha256', 'rtl_sha256', 'source', 'seed')))
    rows = []
    for index, step in enumerate(raw['steps']):
        kind = step['kind']
        if kind == 'request':
            expected = model.translate(step['request'])
        elif kind == 'command':
            model.enqueue(step['command'])
            expected = dict(status='queued')
        elif kind == 'process_command':
            expected = model.process_command()
        elif kind == 'pte_write':
            model.memory[number(step['address'])] = number(step['data'])
            expected = dict(status='written')
        elif kind == 'fault_pop':
            expected = model.faults.popleft() if model.faults else None
        else:
            raise ValueError('unsupported IOMMU scenario step')
        if isinstance(expected, dict):
            expected.pop('cached', None)
        actual = observed[index] if observed is not None and index < len(observed) else None
        status = 'inconclusive' if observed is None or index >= len(observed) else 'match' if actual == expected else 'mismatch'
        rows.append(dict(index=index, kind=kind, expected=expected, observed=actual, status=status))
    mismatch = any(r['status'] == 'mismatch' for r in rows) or observed is not None and len(observed) > len(rows)
    return dict(schema='rvw.iommu-check/1', status='mismatch' if mismatch else 'consistent' if bound and rows and all(r['status'] == 'match' for r in rows) else 'inconclusive',
                description_sha256=description_hash, c1_bound=bound,
                upstream=UPSTREAM, steps=rows, fault_overflow=model.overflow,
                scope='decoded contexts, scalar translation, decoded queues and page MSI remapping; no raw DDT/PDT or register conformance')


def mcp_run(description, observations=None, result=None):
    return run(description, observations, result)


def generate(seed=1, mode='sv39'):
    """Generate a bounded decoded translation/isolation/queue/MSI campaign."""
    import random
    from .mmu import ROOT, DATA
    from .mmu_paging import page_tables
    if mode not in ('sv39', 'sv48', 'sv57'):
        raise ValueError('IOMMU generator supports RV64 first stages')
    pages, leaf = page_tables(dict(mode=mode, level=0), ROOT, DATA, 0xdf)
    memory = {ROOT + d * 4096 + i * 8: p for d, table in enumerate(pages) for i, p in enumerate(table)}
    root = 0x80020000
    # G-stage identity mapping with a 1 GiB leaf, under any supported x4 root.
    from .mmu_paging import MODES
    table = root
    for level in reversed(range(MODES[mode].levels)):
        index = 0x80000000 >> (12 + 9 * level) & (2047 if level == MODES[mode].levels - 1 else 511)
        if level == 2:
            memory[table + index * 8] = (0x80000000 >> 12 << 10) | 0xdf
            break
        memory[table + index * 8] = ((table + 16384) >> 12 << 10) | 1
        table += 16384
    contexts = {1: dict(first=dict(mode=mode, root=ROOT), second=dict(mode=mode, root=root)),
                2: dict(processes={7: dict(mode=mode, root=ROOT)}, second=dict(mode=mode, root=root)),
                3: dict(valid=False),
                4: dict(msi=dict(mask=0xffff0000, pattern=0x24000000, pages={0x24000: 0x28000000}))}
    requests = [dict(device=1, address=0x40000000, access='load'), dict(device=1, address=0x40000000, access='store'),
                dict(device=2, process=7, address=0x40000000, access='load'), dict(device=2, process=8, address=0x40000000, access='load'),
                dict(device=3, address=0x40000000, access='load'), dict(device=99, address=0x40000000, access='load'),
                dict(device=4, address=0x24000004, access='store')]
    random.Random(seed).shuffle(requests)
    steps = [dict(kind='request', request=r) for r in requests]
    steps += [dict(kind='pte_write', address=leaf, data=((DATA + 4096) >> 12 << 10) | 0xdf),
              dict(kind='command', command=dict(op='iotinval', device=1)), dict(kind='process_command'),
              dict(kind='command', command=dict(op='iofence')), dict(kind='process_command'),
              dict(kind='request', request=dict(device=1, address=0x40000000, access='load')), dict(kind='fault_pop')]
    return dict(schema='rvw.iommu-scenarios/1', contexts=contexts, memory=memory, steps=steps, queue_size=8, seed=seed)
