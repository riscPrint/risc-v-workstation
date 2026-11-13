"""Independent scalar page walker and ordered DUT walk comparison.

The caller supplies a memory snapshot for each access. Captured PTE data never
serves as reference memory. Extension PTEs and hardware A/D writes are refused.
"""
from .mmu import number
from .mmu_paging import MODES


def walk(*, mode, root, va, access, memory, privilege='S', sum=False,
         mxr=False, denied=(), x4=False, pte_reader=None):
    g = MODES[mode]
    va, table = number(va), number(root)
    if access not in ('fetch', 'load', 'store') or privilege not in ('S', 'U'):
        raise ValueError('unsupported access or privilege')
    memory = {number(k): number(v) for k, v in memory.items()}
    denied = {number(a) for a in denied}
    reads = []
    def result(status, **kw):
        return dict(status=status, reads=reads, **kw)
    if not (0 <= va < 1 << (g.va_bits + 2) if x4 else g.canonical(va)):
        return result('page-fault')
    for level in reversed(range(g.levels)):
        address = table + ((va >> (12 + level * g.vpn_bits)) & ((1 << (g.vpn_bits + (2 if x4 and level == g.levels - 1 else 0))) - 1)) * g.width
        if address in denied:
            reads.append(dict(level=level, address=address, fault=True))
            return result('access-fault')
        if pte_reader is None and address not in memory:
            raise ValueError(f'missing reference PTE at {address:#x}')
        pte = pte_reader(address) if pte_reader else memory[address]
        if not 0 <= pte < 1 << g.xlen:
            raise ValueError('PTE is outside XLEN')
        reads.append(dict(level=level, address=address, data=pte, fault=False))
        if g.xlen == 64 and pte >> 54:
            raise ValueError('extension or reserved PTE bits are unsupported')
        if not pte & 1 or pte & 4 and not pte & 2:
            return result('page-fault')
        ppn = pte >> 10
        if pte & 10:
            allowed = bool(pte & (8 if access == 'fetch' else 4 if access == 'store' else 2))
            if access == 'load' and mxr and pte & 8:
                allowed = True
            user = bool(pte & 16)
            allowed &= user if privilege == 'U' else not user or access != 'fetch' and sum
            if not allowed or ppn & ((1 << (level * g.vpn_bits)) - 1) or not pte & 64 or access == 'store' and not pte & 128:
                return result('page-fault')
            offset_bits = 12 + level * g.vpn_bits
            return result('success', pa=(ppn << 12) | (va & ((1 << offset_bits) - 1)))
        if pte & (16 | 64 | 128) or level == 0:
            return result('page-fault')
        table = ppn << 12
    raise AssertionError('unreachable')


def check(records, accesses):
    """Compare completed DUT records with independently declared accesses.

    A missing record is inconclusive. Extra, reordered or incorrect records
    are mismatches. Each access snapshot describes memory at that access.
    """
    records, accesses = list(records), list(accesses)
    if not accesses:
        return dict(status='inconclusive', checked=0, expected=0, reason='no supported reference accesses')
    errors = []
    for index, (record, access) in enumerate(zip(records, accesses)):
        reference = walk(**access)
        if record.get('kind') != 'mmu_walk' or record.get('access_id') != index:
            errors.append(f'access {index}: wrong record kind or access_id')
        for field in ('mode', 'access'):
            if record.get(field) != access[field]:
                errors.append(f'access {index}: wrong {field}')
        if number(record['va']) != number(access['va']) or number(record['root']) != number(access['root']):
            errors.append(f'access {index}: wrong address or root')
        reads = [{k: number(v) if k in ('address', 'data') else v for k, v in r.items()} for r in record['reads']]
        if reads != reference['reads']:
            errors.append(f'access {index}: PTE levels, addresses, data or faults differ')
        if record['status'] != reference['status']:
            errors.append(f'access {index}: wrong walk result')
        if reference['status'] == 'success' and number(record.get('pa', -1)) != reference['pa']:
            errors.append(f'access {index}: wrong physical address')
    if len(records) > len(accesses):
        errors.append('extra DUT walk records')
    return dict(status='mismatch' if errors else 'consistent' if records and len(records) == len(accesses) else 'inconclusive',
                checked=min(len(records), len(accesses)), expected=len(accesses), errors=errors)


def fault_matrix(modes):
    rows = []
    for mode in modes:
        for level in range(MODES[mode].levels):
            for access in ('load', 'store', 'fetch'):
                for field, expect in [('pte_fault_level', 'page-fault'), ('walk_deny_level', 'access-fault')]:
                    rows.append(dict(id=f'{mode}-{field.replace("_", "-")}-{level}-{access}', mode=mode,
                                     level=0, flags='VRWXAD', access=access, expect=expect,
                                     bins=[f'{mode}.{field}', f'{mode}.{field}.{level}.{access}'], **{field: level}))
    return rows


def validate_capture(record):
    """Validate the optional per-retirement C2 mmu_walks record."""
    if not isinstance(record, dict) or record.get('kind') != 'mmu_walk':
        raise ValueError('expected mmu_walk record')
    if type(record.get('access_id')) is not int or record['access_id'] < 0:
        raise ValueError('invalid walk access_id')
    if record.get('mode') not in MODES or record.get('access') not in ('load', 'store', 'fetch'):
        raise ValueError('invalid walk mode or access')
    g = MODES[record['mode']]
    for key in ('va', 'root'):
        if not 0 <= number(record[key]) < 1 << g.xlen:
            raise ValueError('invalid walk address')
    if record.get('status') not in ('success', 'page-fault', 'access-fault'):
        raise ValueError('invalid walk status')
    if record['status'] == 'success' and not 0 <= number(record['pa']) < 1 << (34 if g.xlen == 32 else 56):
        raise ValueError('invalid walk physical address')
    if not isinstance(record.get('reads'), list):
        raise ValueError('walk reads must be a list')
    for read in record['reads']:
        if type(read.get('level')) is not int or read['level'] not in range(g.levels) or type(read.get('fault')) is not bool:
            raise ValueError('invalid PTE level or fault')
        if number(read['address']) < 0 or number(read['address']) % g.width:
            raise ValueError('invalid PTE address')
        if not read['fault'] and not 0 <= number(read['data']) < 1 << g.xlen:
            raise ValueError('invalid PTE data')


def same_run(header, c1):
    """True when a C2 or observation header names the C1 run's core, config, ELF, RTL and seed,
    and every one of its source fields equals C1's. `rvw regress run` adds runner fields
    (adapter, captures, tools key) to C1 `source` after the adapter wrote its header."""
    if not c1.get('rtl_sha256') or any(k not in header or k not in c1 or header[k] != c1[k]
                                       for k in ('core', 'config', 'elf_sha256', 'rtl_sha256', 'seed')):
        return False
    a, b = header.get('source'), c1.get('source')
    return isinstance(a, dict) and isinstance(b, dict) and (a == b or bool(a) and all(k in b and b[k] == v for k, v in a.items()))


def check_c2(path, accesses, identity=None):
    from rvw.cosim.trace import Trace
    trace = Trace(path)
    try:
        if identity is not None and not same_run(trace.header, identity):
            return dict(status='inconclusive', reason='C2 identity differs from C1')
        records, ended = [], False
        for row in trace:
            if row.get('event') == 'end':
                ended = row.get('status') == 'pass'
            elif 'event' not in row:
                records.extend(row.get('mmu_walks', []))
        if not ended:
            return dict(status='inconclusive', reason='missing passing C2 end')
    finally:
        trace.close()
    return check(records, accesses)


def scenario_accesses(s):
    """Build independent snapshots for bounded MPRV data scenarios.

    Root switching and unfenced alternatives need a project-owned access plan.
    Empty plans must not earn a comparison verdict.
    """
    from .mmu import ROOT, DATA, FLAGS
    from .mmu_paging import geometry, page_tables
    if 'random_program' in s:
        from .mmu_random import plan
        p = plan(s)
        g = geometry(s)
        memory = {ROOT + d * 4096 + i * g.width: value for d, table in enumerate(p['tables']) for i, value in enumerate(table)}
        return [dict(mode=s['mode'], root=ROOT, va=0x40000000 + a['page'] * 4096, access=a['access'], memory=memory) for a in p['accesses']]
    if any(k in s for k in ('control', 'guest', 'shootdown', 'pointer_mask', 'pbmt', 'napot', 'ad_expect')) or s.get('access') not in ('load', 'store') or s.get('root_switch') or s.get('switch_asid') or s.get('unfenced') or s.get('mode_switch') or s.get('satp_mode') == 'bare' or not s.get('mprv', True):
        return []
    g = geometry(s)
    flags = sum(FLAGS[f] for f in set(s['flags']))
    if flags & 192 != 192:
        return []
    tables, leaf = page_tables(s, ROOT, number(s.get('pa', DATA)), flags)
    memory = {ROOT + d * 4096 + i * g.width: pte for d, table in enumerate(tables) for i, pte in enumerate(table)}
    denied = []
    if s.get('walk_deny'):
        denied = list(memory)
    elif 'walk_deny_level' in s:
        start = ROOT + (g.levels - 1 - s['walk_deny_level']) * 4096
        denied = [a for a in memory if start <= a < start + 4096]
    first = dict(mode=s.get('mode', 'sv39'), root=ROOT, va=number(s.get('va', 0x40000000)) + s.get('offset', 0),
                 access=s['access'], memory=memory, denied=denied, privilege=s.get('privilege', 'S'),
                 sum=s.get('sum', False), mxr=s.get('mxr', False))
    if s.get('remap'):
        changed = dict(memory)
        changed[leaf] = ((DATA + 4096) >> 12 << 10) | flags
        return [first, dict(first, memory=changed)]
    return [first]
