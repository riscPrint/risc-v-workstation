"""Page-table geometry and bounded requirement matrices, independent of a core."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Geometry:
    xlen: int
    levels: int
    vpn_bits: int
    satp_mode: int
    va_bits: int

    @property
    def width(self):
        return self.xlen // 8

    def canonical(self, va):
        if not 0 <= va < 1 << self.xlen:
            return False
        high = va >> self.va_bits
        return high == ((1 << (self.xlen - self.va_bits)) - 1 if va & (1 << (self.va_bits - 1)) else 0)

    def satp(self, root, asid=0):
        return (self.satp_mode << (31 if self.xlen == 32 else 60)) | (asid << (22 if self.xlen == 32 else 44)) | (root >> 12)


MODES = {'sv32': Geometry(32, 2, 10, 1, 32),
         'sv39': Geometry(64, 3, 9, 8, 39),
         'sv48': Geometry(64, 4, 9, 9, 48),
         'sv57': Geometry(64, 5, 9, 10, 57)}


def geometry(s):
    try:
        return MODES[s.get('mode', 'sv39')]
    except (KeyError, TypeError):
        raise ValueError('mode must be sv32, sv39, sv48 or sv57') from None


def page_tables(s, root, pa, flags):
    """Return allocated table pages and the physical leaf address."""
    g = geometry(s)
    va = int(s.get('va', 0x40000000), 0) if isinstance(s.get('va'), str) else s.get('va', 0x40000000)
    count = g.levels - s['level']
    tables = [[0] * (1 << g.vpn_bits) for _ in range(count)]
    for depth, table in enumerate(tables):
        level = g.levels - 1 - depth
        index = va >> (12 + g.vpn_bits * level) & ((1 << g.vpn_bits) - 1)
        table[index] = (((root + 4096 * (depth + 1)) >> 12) << 10) | 1 | (32 if s.get('nonleaf_global') else 0)
        if level == s['level']:
            from .mmu_extensions import pte
            table[index] = pte(s, pa, flags)
            if s.get('napot'):
                for slot in range(index & ~15, (index & ~15) + 16):
                    table[slot] = table[index]
    if 'pte_fault_level' in s:
        fault_level = s['pte_fault_level']
        depth = g.levels - 1 - fault_level
        index = va >> (12 + g.vpn_bits * fault_level) & ((1 << g.vpn_bits) - 1)
        tables[depth][index] = 0
    leaf = root + (count - 1) * 4096 + ((va >> (12 + g.vpn_bits * s['level'])) & ((1 << g.vpn_bits) - 1)) * g.width
    if s.get('root_switch'):
        alternate, _ = page_tables({**s, 'root_switch': False}, root + count * 4096, pa + 4096, flags)
        tables += alternate
    return tables, leaf


def matrix(config):
    """Expand project-selected modes to explicit, independently checked scenarios.

    This is a bounded matrix, not an exhaustive cross product or DUT evidence.
    """
    if not isinstance(config, dict) or set(config) != {'modes'} or not isinstance(config['modes'], list) or not config['modes']:
        raise ValueError('matrix requires a nonempty modes list')
    if len(set(config['modes'])) != len(config['modes']):
        raise ValueError('duplicate matrix mode')
    rows = []
    for mode in config['modes']:
        g = geometry({'mode': mode})
        def add(name, group, **kw):
            row = dict(id=f'{mode}-{name}', mode=mode, level=0, flags='VRWAD', access='load', expect='success', bins=[f'{mode}.{group}', f'{mode}.{name}'])
            row.update(kw)
            rows.append(row)
        for access in ('load', 'store', 'fetch'):
            for flags, name in [('VRWAD', 'rw'), ('VXAD', 'x'), ('VRWXUAD', 'user'), ('RWXAD', 'invalid'), ('VWAD', 'reserved-w')]:
                for priv in ('S', 'U'):
                    for enabled, mxr in ((False, False), (False, True), (True, False), (True, True)):
                        valid = 'V' in flags and not ('W' in flags and 'R' not in flags)
                        permitted = ('X' in flags if access == 'fetch' else 'W' in flags if access == 'store' else 'R' in flags or mxr and 'X' in flags)
                        permitted &= ('U' in flags if priv == 'U' else 'U' not in flags or access != 'fetch' and enabled)
                        add(f'{access}-{name}-{priv.lower()}-{int(enabled)}-{int(mxr)}', 'permissions', access=access, flags=flags, privilege=priv, sum=enabled, mxr=mxr, expect='success' if valid and permitted else 'page-fault')
        for level in range(g.levels):
            # Keep the physical target DATA for all superpage sizes.
            span = 1 << (12 + g.vpn_bits * level)
            pa = 0x80200000 & -span
            va = (0x40000000 & -span) | (0x80200000 & (span - 1))
            add(f'level-{level}', 'superpages', level=level, pa=pa, va=va)
            if level:
                add(f'level-{level}-misaligned', 'misaligned-superpages', level=level, pa=pa + 4096, va=va, expect='page-fault')
        if g.xlen == 64:
            add('noncanonical-positive', 'canonical', va=1 << (g.va_bits - 1), expect='page-fault')
            add('noncanonical-negative', 'canonical', va=(1 << 64) - (1 << (g.va_bits - 1)) - 4096, expect='page-fault')
            add('canonical-high', 'canonical', va=(1 << 64) - 4096)
        for access in ('load', 'store'):
            add(f'{access}-walk-denied', 'walk-fault', access=access, walk_deny=True, expect='access-fault')
            for ad in ('svade', 'hardware'):
                add(f'{access}-{ad}', 'ad', access=access, flags='VRW', ad_mode=ad, ad_expect=0 if ad == 'svade' else 64 if access == 'load' else 192, expect='page-fault' if ad == 'svade' else 'success')
        add('mode-switch', 'satp', mode_switch=True)
        add('bare', 'satp', va=0x80200000, satp_mode='bare')
        add('mprv-clear', 'mprv', va=0x80200000, mprv=False)
        for fence in ('all', 'va', 'asid', 'va-asid'):
            add(f'remap-{fence}', 'fences', remap=True, fence=fence, asid=7)
            add(f'root-{fence}', 'asid-reuse', remap=True, root_switch=True, fence=fence, asid=7)
        add('global', 'global', flags='VRWGAD', remap=True)
        add('nonleaf-global', 'global', nonleaf_global=True, remap=True)
    return rows
