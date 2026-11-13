"""Explicit PTE extension encodings for project-selected VM scenarios."""


def validate(s, g):
    if 'pbmt' in s and (g.xlen != 64 or type(s['pbmt']) is not int or s['pbmt'] not in range(4)):
        raise ValueError('pbmt requires RV64 and a two-bit encoding')
    if 'pbmt' in s and (s.get('remap') or 'ad_expect' in s):
        raise ValueError('pbmt supports immutable mappings without ad_expect')
    if 'pbmte' in s and ('pbmt' not in s or type(s['pbmte']) is not bool):
        raise ValueError('pbmte requires pbmt and a boolean')
    if 'napot' in s and (g.xlen != 64 or type(s['napot']) is not bool):
        raise ValueError('napot requires RV64 and a boolean')
    if 'napot_ppn' in s and (not s.get('napot') or type(s['napot_ppn']) is not int or not 0 <= s['napot_ppn'] < 16):
        raise ValueError('napot_ppn requires napot and a four-bit PPN encoding')
    if s.get('napot') and (s['level'] != 0 or s.get('remap') or s['access'] == 'fetch' or 'ad_expect' in s):
        raise ValueError('napot supports immutable level-zero data accesses')


def pte(s, pa, flags):
    if s.get('napot'):
        # The standard 64 KiB encoding has PPN[3:0] = 1000.
        pa = (pa & ~0xffff) | (s.get('napot_ppn', 8) << 12)
    return ((pa >> 12) << 10) | flags | (s.get('pbmt', 0) << 61) | (int(s.get('napot', False)) << 63)


def setup(s):
    if 'pbmt' in s:
        return 'li t0, 0x4000000000000000\n ' + ('csrs' if s.get('pbmte', True) else 'csrc') + ' menvcfg, t0\n'
    return ''


def isa(s):
    return ('_svnapot' if 'napot' in s else '') + ('_svpbmt' if 'pbmt' in s else '')
