"""Declarative, self-checking virtual-memory programs."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from rvw.common.proc import run_group
from rvw.regress.run_evidence import run_paths_under

SPEC = 'https://docs.riscv.org/reference/isa/v20260120/priv/supervisor.html'
FLAGS = dict(zip('VRWXUGAD', (1, 2, 4, 8, 16, 32, 64, 128)))
ROOT = 0x80010000
DATA = 0x80200000
LINK = '''OUTPUT_ARCH("riscv")
ENTRY(_start)
SECTIONS {
 . = 0x80000000; .text : { *(.text) }
 . = 0x80008000; .tohost : { *(.tohost) }
 . = 0x80010000; .tables : { *(.tables) }
 . = 0x80200000; .data : { *(.data) }
}
'''


def number(value):
    if isinstance(value, str):
        return int(value, 0)
    if type(value) is not int:
        raise ValueError('expected an integer or integer string')
    return value


def load(path):
    raw = json.loads(Path(path).read_text())
    if set(raw) == {'schema', 'guest_pointer_matrix'} and raw['schema'] == 'rvw.mmu/1':
        from .mmu_guest_pointer import matrix as guest_pointer_matrix
        raw = dict(schema=raw['schema'], scenarios=guest_pointer_matrix(raw['guest_pointer_matrix']))
    if set(raw) == {'schema', 'random'} and raw['schema'] == 'rvw.mmu/1':
        from .mmu_random import matrix as random_matrix
        raw = dict(schema=raw['schema'], scenarios=random_matrix(raw['random']))
    if set(raw) == {'schema', 'pointer_matrix'} and raw['schema'] == 'rvw.mmu/1':
        from .mmu_pointer import matrix as pointer_matrix
        raw = dict(schema=raw['schema'], scenarios=pointer_matrix(raw['pointer_matrix']))
    if set(raw) == {'schema', 'guest_matrix'} and raw['schema'] == 'rvw.mmu/1':
        from .mmu_hypervisor import matrix as guest_matrix
        raw = dict(schema=raw['schema'], scenarios=guest_matrix(raw['guest_matrix']))
    if set(raw) == {'schema', 'matrix'} and raw['schema'] == 'rvw.mmu/1':
        from .mmu_paging import matrix
        raw = dict(schema=raw['schema'], scenarios=matrix(raw['matrix']))
    if set(raw) != {'schema', 'scenarios'} or raw['schema'] != 'rvw.mmu/1':
        raise ValueError('expected rvw.mmu/1 with scenarios')
    if not isinstance(raw['scenarios'], list) or not raw['scenarios']:
        raise ValueError('scenarios must be a nonempty list')
    ids = set()
    for s in raw['scenarios']:
        validate(s)
        if s['id'] in ids:
            raise ValueError('duplicate scenario id')
        ids.add(s['id'])
    return raw['scenarios']


def validate(s):
    if isinstance(s, dict) and 'random_program' in s:
        from .mmu_random import validate as validate_random
        return validate_random(s)
    if isinstance(s, dict) and 'control' in s:
        return control_validate(s)
    from .mmu_paging import geometry
    g = geometry(s)
    required = {'id', 'level', 'flags', 'access', 'expect', 'bins'}
    optional = {'pmp_regions', 'guest_pointer', 'napot_remap', 'pointer_extension', 'pointer_controller', 'guest_trap', 'guest_switch', 'guest_mode', 'guest_op', 'atomic_ad', 'ipi', 'pte_fault_level', 'walk_deny_level', 'pointer_mask', 'shootdown', 'guest', 'guest_flags', 'guest_fault', 'vmid', 'napot_ppn', 'napot', 'pbmt', 'pbmte', 'mode_switch', 'mode', 'va', 'pa', 'privilege', 'sum', 'mxr', 'ad_expect', 'asid', 'fence', 'remap', 'ad_mode', 'satp_mode', 'mprv', 'offset', 'walk_deny', 'unfenced', 'switch_asid', 'value', 'access_width', 'register_width', 'root_switch', 'nonleaf_global', 'software_rsw', 'store_value'}
    if not isinstance(s, dict) or not required <= s.keys() or s.keys() - required - optional:
        raise ValueError('invalid scenario fields')
    regions = s.get('pmp_regions', 1)
    if type(regions) is not int or regions < 0:
        raise ValueError('pmp_regions must be a nonnegative integer')
    if regions == 0 and (s.get('walk_deny') or 'walk_deny_level' in s):
        raise ValueError('walk denial requires PMP regions')
    if regions == 0 and any(k in s for k in ('guest', 'guest_pointer', 'shootdown', 'atomic_ad', 'napot_remap')):
        raise ValueError('pmp_regions=0 requires a base translation scenario')
    if not re.fullmatch(r'[a-z][a-z0-9-]*', s['id']):
        raise ValueError('invalid scenario id')
    if type(s['level']) is not int or s['level'] not in range(g.levels):
        raise ValueError('level is outside the selected paging mode')
    from .mmu_extensions import validate as validate_extensions
    validate_extensions(s, g)
    for key in ('pte_fault_level', 'walk_deny_level'):
        if key in s:
            if type(s[key]) is not int or not s['level'] <= s[key] < g.levels:
                raise ValueError(f'{key} must name an allocated walk level')
            if s['expect'] != ('page-fault' if key == 'pte_fault_level' else 'access-fault') or s.get('remap') or s.get('walk_deny'):
                raise ValueError(f'{key} requires its fault expectation without remap/walk_deny')
    if 'mode_switch' in s and (type(s['mode_switch']) is not bool or s['access'] != 'load' or s.get('remap') or s['expect'] != 'success' or number(s.get('pa', DATA)) != DATA or s.get('value', 42) != 42 or s.get('offset', 0)):
        raise ValueError('mode_switch requires a successful data access without remap')
    if not isinstance(s['flags'], str) or set(s['flags']) - FLAGS.keys():
        raise ValueError('invalid PTE flags')
    if s['access'] not in ('load', 'store', 'fetch') or s['expect'] not in ('success', 'page-fault', 'access-fault', 'misaligned', 'virtual-instruction'):
        raise ValueError('unsupported access or expectation')
    if s['expect'] == 'virtual-instruction' and not s.get('guest_op', '').startswith('vs-'):
        raise ValueError('virtual-instruction requires a VS control operation')
    if s['access'] == 'fetch' and (s['expect'] not in ('success', 'page-fault', 'access-fault') or any(k in s for k in ('remap', 'unfenced', 'switch_asid', 'offset', 'access_width', 'register_width', 'mprv', 'satp_mode', 'ad_expect')) or number(s.get('pa', DATA)) != DATA):
        raise ValueError('fetch requires a fixed payload at DATA and no data-only options')
    width = s.get('access_width', g.width)
    if type(width) is not int or width not in (1, 2, 4, 8) or width > g.width:
        raise ValueError('access_width must be 1, 2, 4 or 8 bytes')
    if 'register_width' in s:
        bits = s['register_width']
        if type(bits) is not int or bits not in (8, 16, 32, 64):
            raise ValueError('register width must be 8, 16, 32 or 64 bits')
        if width * 8 > bits:
            raise ValueError('access exceeds declared register width')
    if width != g.width and s.get('remap'):
        raise ValueError('remap requires a native-width access')
    if s.get('privilege', 'S') not in ('S', 'U'):
        raise ValueError('privilege must be S or U')
    for key in ('sum', 'mxr', 'mprv', 'walk_deny', 'unfenced', 'switch_asid', 'root_switch', 'nonleaf_global'):
        if key in s and type(s[key]) is not bool:
            raise ValueError(f'{key} must be boolean')
    for key in ('va', 'pa'):
        n = number(s.get(key, 0x40000000 if key == 'va' else DATA))
        if not 0 <= n < 2**64 or n % 4096:
            raise ValueError(f'{key} must be an unsigned page address')
    if s.get('satp_mode', 'sv39') not in ('sv39', 'bare'):
        raise ValueError('satp_mode must be sv39 or bare')
    if s.get('satp_mode') == 'bare' and (s.get('asid', 0) or s.get('remap')):
        raise ValueError('bare mode requires ASID zero and no remap')
    if s.get('remap', False):
        if s['level'] != 0 or s['access'] != 'load' or s['expect'] != 'success' or number(s.get('pa', DATA)) != DATA:
            raise ValueError('remap requires a successful level-0 load from DATA')
        if ('G' in s['flags'] or s.get('nonleaf_global')) and s.get('fence', 'all') not in ('all', 'va'):
            raise ValueError('global remap requires an all-ASID fence')
    if s.get('nonleaf_global') and s['level'] == g.levels - 1:
        raise ValueError('nonleaf_global requires a non-leaf PTE')
    if s.get('root_switch') and (not s.get('remap') or s.get('unfenced') or s.get('switch_asid')):
        raise ValueError('root_switch requires remap and excludes unfenced/switch_asid')
    if 'remap' in s and type(s['remap']) is not bool:
        raise ValueError('remap must be boolean')
    if 'store_value' in s and (s['access'] != 'store' or type(s['store_value']) is not int or not 0 <= s['store_value'] < 2**31):
        raise ValueError('store_value must be a nonnegative signed 32-bit store value')
    if type(s.get('value', 42)) is not int or not 0 <= s.get('value', 42) < 2**63:
        raise ValueError('value must be a nonnegative signed 64-bit integer')
    if type(s.get('offset', 0)) is not int or not 0 <= s.get('offset', 0) <= 4088:
        raise ValueError('offset must be in 0..4088')
    if any(s.get(k) for k in ('unfenced', 'switch_asid')) and not s.get('remap'):
        raise ValueError('unfenced and switch_asid require remap')
    va = number(s.get('va', 0x40000000))
    if not g.canonical(va) and (s.get('mode') is None or s['expect'] != 'page-fault' or s.get('satp_mode') == 'bare' or not s.get('mprv', True)):
        raise ValueError('va must be canonical or explicitly test a page fault')
    if not isinstance(s['bins'], list) or not s['bins'] or any(not isinstance(b, str) or not b for b in s['bins']):
        raise ValueError('bins must be nonempty strings')
    if 'software_rsw' in s and (type(s['software_rsw']) is not int or not 0 <= s['software_rsw'] <= 3 or 'ad_expect' not in s or s.get('remap') or s['access'] == 'fetch'):
        raise ValueError('software_rsw requires 0..3 and ad_expect, without remap/fetch')
    if 'ad_expect' in s and (type(s['ad_expect']) is not int or s['ad_expect'] & ~192):
        raise ValueError('ad_expect must contain only A/D bits')
    if type(s.get('asid', 0)) is not int or not 0 <= s.get('asid', 0) < (512 if g.xlen == 32 else 65536):
        raise ValueError('asid must fit 16 bits')
    if s.get('ad_mode', 'hardware') not in ('hardware', 'svade'):
        raise ValueError('ad_mode must be hardware or svade')
    if 'ipi' in s and not s.get('shootdown'):
        raise ValueError('ipi requires shootdown')
    if 'napot_remap' in s:
        from .mmu_napot_range import validate as validate_napot_range
        validate_napot_range(s)
    if 'atomic_ad' in s:
        from .mmu_atomic import validate as validate_atomic
        validate_atomic(s)
    if 'pointer_mask' in s:
        from .mmu_pointer import validate as validate_pointer
        validate_pointer(s)
    if 'shootdown' in s:
        from .mmu_shootdown import validate as validate_shootdown
        validate_shootdown(s)
    if 'guest' in s:
        from .mmu_guest import validate as validate_guest
        validate_guest(s)
    if s.get('fence', 'all') not in ('all', 'va', 'asid', 'va-asid'):
        raise ValueError('unsupported fence scope')


def assembly(s):
    if 'random_program' in s:
        from .mmu_random import assembly as random_assembly
        return random_assembly(s)
    if 'control' in s:
        return control_assembly(s)
    validate(s)
    if s.get('napot_remap'):
        from .mmu_napot_range import assembly as napot_range_assembly
        return napot_range_assembly(s)
    if s.get('atomic_ad'):
        from .mmu_atomic import assembly as atomic_assembly
        return atomic_assembly(s)
    if s.get('shootdown'):
        from .mmu_shootdown import assembly as shootdown_assembly
        return shootdown_assembly(s)
    if 'guest_pointer' in s:
        from .mmu_guest_pointer import assembly as guest_pointer_assembly
        return guest_pointer_assembly(s)
    if s.get('guest'):
        from .mmu_guest import assembly as guest_assembly
        return guest_assembly(s)
    va = number(s.get('va', 0x40000000))
    pa = number(s.get('pa', DATA))
    load_op = {1: 'lb', 2: 'lh', 4: 'lw', 8: 'ld'}[s.get('access_width', 4 if s.get('mode') == 'sv32' else 8)]
    store_op = {1: 'sb', 2: 'sh', 4: 'sw', 8: 'sd'}[s.get('access_width', 4 if s.get('mode') == 'sv32' else 8)]
    level = s['level']
    from .mmu_paging import geometry, page_tables
    g = geometry(s)
    tables, leaf = page_tables(s, ROOT, pa, sum(FLAGS[f] for f in set(s['flags'])))
    va += s.get('offset', 0)
    if 'pointer_mask' in s:
        va |= 1 << 63
    fault = s['expect'] != 'success'
    cause = {'page-fault': (13, 15), 'access-fault': (5, 7), 'misaligned': (4, 6), 'success': (0, 0)}[s['expect']][s['access'] == 'store']
    status = (int(s.get('mprv', True)) << 17) | ((1 if s.get('privilege', 'S') == 'S' else 0) << 11)
    status |= int(s.get('sum', False)) << 18 | int(s.get('mxr', False)) << 19
    asid = s.get('asid', 0)
    fence = {'all': 'sfence.vma x0, x0', 'va': 'sfence.vma t3, x0',
             'asid': 'sfence.vma x0, t4', 'va-asid': 'sfence.vma t3, t4'}[s.get('fence', 'all')]
    denied_start = ROOT + (g.levels - 1 - s.get('walk_deny_level', g.levels - 1)) * 4096
    denied_end = denied_start + (4096 if 'walk_deny_level' in s else len(tables) * 4096)
    # All fetches stay in M-mode. MPRV selects S/U only for the tested data access.
    code = f'''.option norvc
.section .text
.globl _start
_start:
 la t0, trap
 csrw mtvec, t0
 csrw mie, zero
 csrw medeleg, zero
 csrw mideleg, zero
 li t0, -1
 csrw pmpaddr0, t0
 li t0, 15
 csrw pmpcfg0, t0
 {('li t0, ' + str(denied_start >> 2) + chr(10) + ' csrw pmpaddr0, t0' + chr(10) + ' li t0, ' + str(denied_end >> 2) + chr(10) + ' csrw pmpaddr1, t0' + chr(10) + ' li t0, -1' + chr(10) + ' csrw pmpaddr2, t0' + chr(10) + ' li t0, 0x0f080f' + chr(10) + ' csrw pmpcfg0, t0') if s.get('walk_deny') or 'walk_deny_level' in s else ''}
 li t0, {0 if s.get('satp_mode') == 'bare' else g.satp(ROOT, asid)}
 csrw satp, t0
 {('li t0, ' + str(leaf) + chr(10) + ' ld t1, 0(t0)' + chr(10) + ' li t2, ' + str(s.get('software_rsw', 0) << 8) + chr(10) + ' or t1, t1, t2' + chr(10) + ' sd t1, 0(t0)') if 'software_rsw' in s else ''}
 {('li t0, 0x2000000000000000' + chr(10) + ' csrs menvcfg, t0') if s.get('ad_mode') == 'hardware' else ''}
 sfence.vma x0, x0
 li t3, {va}
 li t4, {asid}
 {fence}
 li t0, 0xe1800
 csrc mstatus, t0
 li t0, {status}
 csrs mstatus, t0
 li a0, {s.get('store_value', 43) if s['access'] == 'store' else -1}
access_site:
 {load_op if s['access'] == 'load' else store_op} a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 {'j fail' if fault else 'j check_data'}
trap:
 li t0, 0x20000
 csrc mstatus, t0
 {'j check_trap' if fault else 'j fail'}
check_trap:
 csrr t0, mcause
 li t1, {cause}
 bne t0, t1, fail
 csrr t0, mtval
 li t1, {va}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access_site
 bne t0, t1, fail
 j check_ad
check_data:
'''
    if s['access'] == 'store':
        physical = pa | (va & ((1 << (12 + g.vpn_bits * level)) - 1))
        code += f' li t0, {physical}\n {load_op} a0, 0(t0)\n'
    expected = s.get('value', 42)
    if s['access'] == 'store':
        bits = 8 * s.get('access_width', g.width)
        expected = s.get('store_value', 43) & ((1 << bits) - 1)
        if expected & (1 << (bits - 1)):
            expected -= 1 << bits
    code += f" li t1, {expected}\n bne a0, t1, fail\n"
    if s.get('remap', False):
        replacement = (((DATA + 4096) >> 12) << 10) | sum(FLAGS[f] for f in set(s['flags']))
        if s.get('root_switch'):
            # Same ASID, different root. Fence each transition, including reuse.
            for root, value in ((ROOT + (g.levels - level) * 4096, 43), (ROOT, 42), (ROOT + (g.levels - level) * 4096, 43)):
                code += f''' li t0, {g.satp(root, asid)}
 csrw satp, t0
 {fence}
 li t0, {status}
 csrs mstatus, t0
 ld a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 li t1, {value}
 bne a0, t1, fail
'''
        else:
            code += f''' li t0, {leaf}
 li t1, {replacement}
 sd t1, 0(t0)
'''
        if s.get('unfenced'):
            code += f''' li t0, {status}
 csrs mstatus, t0
 ld a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 li t1, 42
 beq a0, t1, stale_allowed
 li t1, 43
 bne a0, t1, fail
stale_allowed:
'''
        if s.get('switch_asid'):
            for other in ((asid + 1) % (512 if g.xlen == 32 else 65536), asid):
                code += f''' li t0, {g.satp(ROOT, other)}
 csrw satp, t0
 {fence}
 li t0, {status}
 csrs mstatus, t0
 ld a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 li t1, 43
 bne a0, t1, fail
'''
        code += f''' {fence}
 li t0, {status}
 csrs mstatus, t0
 ld a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 li t1, 43
 bne a0, t1, fail
'''
    if s.get('mode_switch'):
        code += f''' csrw satp, zero
 sfence.vma x0, x0
 li t3, {DATA}
 li t0, {status}
 csrs mstatus, t0
 ld a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 li t1, 42
 bne a0, t1, fail
 li t0, {g.satp(ROOT, asid)}
 csrw satp, t0
 sfence.vma x0, x0
 li t3, {va}
 li t0, {status}
 csrs mstatus, t0
 ld a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 li t1, 42
 bne a0, t1, fail
'''
    code += 'check_ad:\n'
    if 'ad_expect' in s:
        expected_pa = DATA + 4096 if s.get('remap') and not s.get('root_switch') else pa
        expected_pte = (((expected_pa >> 12) << 10) | sum(FLAGS[f] for f in set(s['flags'])) | (s.get('software_rsw', 0) << 8)) & ~192 | s['ad_expect']
        code += f' li t0, {leaf}\n ld t0, 0(t0)\n li t1, {expected_pte}\n bne t0, t1, fail\n'
    code += ''' li t1, 1
 j finish
fail:
 li t1, 3
finish:
 la t0, tohost
 sd t1, 0(t0)
1: j 1b
.section .tohost,"aw"
.balign 64
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
.section .tables,"aw"
'''
    for table in tables:
        code += '\n'.join(f' {".word" if g.xlen == 32 else ".dword"} {v}' for v in table) + '\n'
    code += '.section .data\n .dword 42\n .zero 4088\n .dword 43\n'
    if s['access'] == 'fetch':
        # MRET changes real fetch privilege. MPRV cannot test instruction access.
        begin = code.index(' li a0,')
        end = code.index('check_ad:')
        expected = 9 if not fault and s.get('privilege', 'S') == 'S' else 8 if not fault else 12 if s['expect'] == 'page-fault' else 1
        code = code[:begin] + f''' csrw mepc, t3
 mret
trap:
 li t0, 0x20000
 csrc mstatus, t0
 csrr t0, mcause
 li t1, {expected}
 bne t0, t1, fail
 csrr t0, mepc
 li t1, {va}
 bne t0, t1, fail
''' + (f' csrr t0, mtval\n li t1, {va}\n bne t0, t1, fail\n' if fault else '') + code[end:]
        code = code.replace('.section .data\n .dword 42\n .zero 4088\n .dword 43\n', '.section .data\n .word 0x00000073\n .word 0x0000006f\n')
    if 'pointer_mask' in s:
        from .mmu_pointer import setup as pointer_setup
        code = code.replace(' sfence.vma x0, x0', ' ' + pointer_setup(s) + 'sfence.vma x0, x0', 1)
    from .mmu_extensions import setup
    code = code.replace(' sfence.vma x0, x0', ' ' + setup(s) + 'sfence.vma x0, x0', 1)
    if 'mode' in s and s.get('satp_mode') != 'bare':
        code = code.replace(' csrw satp, t0', ' csrw satp, t0\n csrr t1, satp\n bne t0, t1, fail', 1)
    if g.xlen == 32:
        code = re.sub(r'\bld\b', 'lw', code)
        code = re.sub(r'\bsd\b', 'sw', code)
        code = code.replace('li t0, 0x2000000000000000\n csrs menvcfg, t0', 'li t0, 0x20000000\n csrs menvcfgh, t0')
    if s.get('pmp_regions', 1) == 0:
        code = code.replace(' li t0, -1\n csrw pmpaddr0, t0\n li t0, 15\n csrw pmpcfg0, t0\n', '', 1)
    return code


def control_validate(s):
    required = {'id', 'control', 'enabled', 'instruction', 'privilege', 'bins'}
    if not required <= s.keys() or s.keys() - required - {'wakeup'} or not re.fullmatch(r'[a-z][a-z0-9-]*', s['id']):
        raise ValueError('invalid control scenario fields')
    choices = {'tvm': ('satp-read', 'satp-write', 'sfence'), 'tw': ('wfi',), 'tsr': ('sret',), 'satp-mode': ('reserved-mode-write',)}
    if s['control'] not in choices or s['instruction'] not in choices[s['control']]:
        raise ValueError('unsupported control instruction')
    if type(s['enabled']) is not bool or s['privilege'] not in (('M',) if s['control'] == 'satp-mode' else ('S', 'U')):
        raise ValueError('invalid control state or privilege')
    if s['control'] == 'satp-mode' and s['enabled']:
        raise ValueError('satp-mode does not use an mstatus control bit')
    if s.get('wakeup') is not None and (s['control'] != 'tw' or s['enabled'] or s['privilege'] != 'S' or s['wakeup'] != 'pending-ssip'):
        raise ValueError('wakeup requires TW-clear S-mode WFI with pending-ssip')
    if s['control'] == 'tw' and not s['enabled'] and s.get('wakeup') != 'pending-ssip':
        raise ValueError('TW-clear WFI needs an interrupt schedule')
    if not isinstance(s['bins'], list) or not s['bins'] or any(not isinstance(b, str) or not b for b in s['bins']):
        raise ValueError('bins must be nonempty strings')


def satp_warl_assembly():
    """Unsupported MODE writes must leave every satp field unchanged."""
    initial = (8 << 60) | (ROOT >> 12)
    reserved = (1 << 60) | (7 << 44) | ((ROOT + 4096) >> 12)
    return f''' .option norvc
.section .text
.globl _start
_start:
 la t0, fail
 csrw mtvec, t0
 csrw mie, zero
 li t0, {initial}
 csrw satp, t0
 csrr t2, satp
 li t1, {initial}
 bne t2, t1, fail
 li t0, {reserved}
 csrw satp, t0
 csrr t0, satp
 bne t0, t2, fail
 li t1, 1
 j finish
fail:
 li t1, 3
finish:
 csrw satp, zero
 sfence.vma x0, x0
 la t0, tohost
 sd t1, 0(t0)
1: j 1b
.section .tohost,"aw"
.balign 64
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
'''


def control_assembly(s):
    control_validate(s)
    if s['control'] == 'satp-mode':
        return satp_warl_assembly()
    bit = {'tvm': 20, 'tw': 21, 'tsr': 22}[s['control']]
    denied = s['enabled'] or s['privilege'] == 'U'
    instruction = {'satp-read': 'csrr a0, satp', 'satp-write': 'csrw satp, zero',
                   'sfence': 'sfence.vma x0, x0', 'wfi': 'wfi', 'sret': 'sret'}[s['instruction']]
    wakeup = 'li t0, 2\n csrw mideleg, t0\n csrw mie, t0\n csrs mip, t0' if s.get('wakeup') else ''
    # Successful SRET returns to S. ECALL then gives a checked M-mode exit.
    return f'''.option norvc
.section .text
.globl _start
_start:
 la t0, trap
 csrw mtvec, t0
 csrw mie, zero
 csrw medeleg, zero
 csrw mideleg, zero
 csrw satp, zero
 li t0, -1
 csrw pmpaddr0, t0
 li t0, 15
 csrw pmpcfg0, t0
 li t0, 0x7e190a
 csrc mstatus, t0
 {wakeup}
 li t0, {(int(s['enabled']) << bit) | (int(s['privilege'] == 'S') << 11) | 256}
 csrs mstatus, t0
 la t0, done
 csrw sepc, t0
 la t0, access_site
 csrw mepc, t0
 mret
access_site:
 {instruction}
 {'j fail' if s['instruction'] == 'sret' else 'nop'}
done:
 ecall
 j fail
trap:
 csrr t0, mcause
 li t1, {2 if denied else 9}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'access_site' if denied else 'done'}
 bne t0, t1, fail
 li t1, 1
 j finish
fail:
 li t1, 3
finish:
 la t0, tohost
 sd t1, 0(t0)
1: j 1b
.section .tohost,"aw"
.balign 64
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_pma(path):
    raw = json.loads(Path(path).read_text())
    if set(raw) != {'schema', 'regions'} or raw['schema'] != 'rvw.mmu-pma/1':
        raise ValueError('expected rvw.mmu-pma/1')
    regions = raw['regions']
    if not isinstance(regions, list) or not regions:
        raise ValueError('PMA regions must be nonempty')
    spans = []
    fields = {'name', 'start', 'size', 'widths', 'read', 'write', 'execute', 'idempotent', 'cacheable', 'atomic'}
    for r in regions:
        if not isinstance(r, dict) or set(r) != fields:
            raise ValueError('invalid PMA region fields')
        start, size = number(r['start']), number(r['size'])
        if start < 0 or size <= 0 or start + size > 2**64:
            raise ValueError('invalid PMA range')
        if not isinstance(r['name'], str) or not r['name']:
            raise ValueError('PMA region needs a name')
        if not isinstance(r['widths'], list) or not r['widths'] or any(type(w) is not int or w not in (1, 2, 4, 8, 16) for w in r['widths']):
            raise ValueError('invalid PMA widths')
        if any(type(r[k]) is not bool for k in ('read', 'write', 'execute', 'idempotent', 'cacheable', 'atomic')):
            raise ValueError('PMA attributes must be boolean')
        if any(start < end and begin < start + size for begin, end in spans):
            raise ValueError('overlapping PMA regions need a resolved platform policy')
        spans.append((start, start + size))
    return raw


def build(description, out, gcc, pma=None):
    scenarios = load(description)
    attributes = read_pma(pma) if pma else None
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Refuse stale ELFs from an earlier description.
    if any(out.iterdir()):
        raise ValueError('build output must be empty')
    (out / 'link.ld').write_text(LINK)
    rows = []
    for s in scenarios:
        source = out / (s['id'] + '.S')
        elf = out / (s['id'] + '.elf')
        source.write_text(assembly(s))
        from .mmu_paging import geometry
        g = geometry(s)
        command = [gcc, f'-march=rv{g.xlen}im' + ('a' if s.get('atomic_ad') else '') + ('h' if s.get('guest') else '') + '_zicsr_zifencei', '-mabi=' + ('ilp32' if g.xlen == 32 else 'lp64'), '-nostdlib', '-nostartfiles',
                   '-static', '-Wl,--no-relax', '-T', str(out / 'link.ld'), '-o', str(elf), str(source)]
        result = run_group(command, capture=True, timeout=60)
        if result.returncode:
            raise ValueError(f'compiler failed for {s["id"]}: {result.stderr}')
        rows.append(dict(s, elf=elf.name, elf_sha256=digest(elf), source_sha256=digest(source)))
    manifest = {'schema': 'rvw.mmu-build/1', 'spec': SPEC, 'description_sha256': digest(description),
                'scenarios': rows, 'pma': attributes, 'pma_sha256': digest(pma) if pma else None}
    from .mmu_cov import groups
    (out / 'functional-groups.json').write_text(json.dumps(groups(), indent=2) + '\n')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def reference(directory, spike, timeout):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    executable = shutil.which(spike)
    if not executable:
        raise ValueError('Spike executable not found')
    executable = str(Path(executable).resolve())
    executable_sha256 = digest(executable)
    version = run_group([executable, '--help'], capture=True, timeout=10)
    rows = []
    for s in manifest['scenarios']:
        elf = directory / s['elf']
        if digest(elf) != s['elf_sha256']:
            raise ValueError('ELF differs from build manifest')
        from .mmu_paging import geometry
        isa = f'rv{geometry(s).xlen}im_zicsr_zifencei' + ('_svade' if s.get('ad_mode') == 'svade' else '_svadu' if s.get('ad_mode') == 'hardware' else '')
        from .mmu_extensions import isa as extension_isa
        isa += extension_isa(s)
        if 'pointer_mask' in s:
            isa += '_' + s.get('pointer_controller', s.get('pointer_extension', 'smnpm'))
        if 'guest_pointer' in s:
            isa += '_ssnpm'
        if s.get('guest'):
            isa = isa.replace('im_', 'imh_')
        command = [executable, '--isa=' + isa, '--priv=msu', '-m128', str(elf)]
        if s.get('atomic_ad'):
            command[1] = command[1].replace('im_', 'ima_')
            if '_svadu' not in command[1]:
                command[1] += '_svadu'
        if s.get('shootdown') or s.get('atomic_ad'):
            command.insert(1, '-p2')
        r = run_group(command, capture=True, timeout=timeout)
        status = ('inconclusive' if r.timed_out else 'pass' if r.returncode == 0 else
                  'fail' if re.search(r'\*\*\* FAILED \*\*\* \(tohost = [0-9a-fx]+\)', r.stderr or '') else 'inconclusive')
        rows.append({'id': s['id'], 'status': status, 'elf_sha256': s['elf_sha256'],
                     'command': command, 'returncode': r.returncode, 'stderr': r.stderr,
                     'bins': {b: status for b in s['bins']}})
    if digest(executable) != executable_sha256:
        raise ValueError('Spike executable changed during reference run')
    return {'schema': 'rvw.mmu-reference/1', 'model': 'spike',
            'executable': executable, 'executable_sha256': executable_sha256,
            'version': ((version.stderr or '') + (version.stdout or '')).splitlines()[:1], 'scope': 'self-checking architectural effects only',
            'status': 'fail' if any(r['status'] == 'fail' for r in rows) else 'pass' if rows and all(r['status'] == 'pass' for r in rows) else 'inconclusive',
            'scenarios': rows}


def check(directory, results, platform, model, timeout, sail=None):
    """Require a conclusive self-check and a complete, strict oracle match."""
    import sys
    from rvw.results import load_run
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    runs = [load_run(p) for p in run_paths_under(results)]
    rows = []
    for s in manifest['scenarios']:
        elf = directory / s['elf']
        if digest(elf) != s['elf_sha256']:
            raise ValueError('ELF differs from build manifest')
        candidates = [r for r in runs if r.elf_sha256 == s['elf_sha256']]
        c1_sha256 = None
        c1_status = None
        status, reason, comparison = 'inconclusive', 'need exactly one C1 result for this ELF', None
        if len(candidates) == 1:
            run = candidates[0]
            c1_status = run.status
            c1_sha256 = digest(run.path / 'result.json')
            reason = run.why_inconclusive
            if not reason and run.status != 'pass':
                status, reason = 'fail', 'C1 self-check failed: ' + run.status
            elif not reason:
                trace = run.artifacts.get('rvfi_trace')
                if not trace or not (run.path / trace).is_file():
                    reason = 'missing C2 trace'
                else:
                    # The explicit platform supplies the oracle; use a generic label
                    # so the child does not require project discovery.
                    command = [sys.executable, '-m', 'rvw', 'cosim', 'check', '--core', 'reference', '--elf', str(elf),
                               '--trace', str(run.path / trace), '--platform', str(Path(platform).resolve()),
                               '--model', model, '--strict', '--timeout', str(timeout), '--json']
                    if sail:
                        command += ['--sail', sail]
                    result = run_group(command, capture=True, timeout=timeout + 10)
                    try:
                        comparison = json.loads(result.stdout or '{}')
                    except ValueError:
                        comparison = {}
                    reason = 'oracle did not establish a complete strict match'
                    if not result.timed_out and comparison.get('status') == 'mismatch':
                        if s.get('unfenced'):
                            status, reason = 'inconclusive', 'strict model divergence in a scenario with permitted unfenced alternatives'
                        else:
                            status, reason = 'fail', 'architectural mismatch'
                    elif (not result.timed_out and result.returncode == 0
                          and comparison.get('status') == 'match'
                          and comparison.get('trace_complete') is True
                          and comparison.get('end_status') == 'pass'
                          and comparison.get('instructions', 0) > 0
                          and comparison.get('synchronized') == 0):
                        status, reason = 'pass', None
        rows.append({'id': s['id'], 'elf_sha256': s['elf_sha256'], 'status': status,
                     'reason': reason, 'comparison': comparison, 'c1_sha256': c1_sha256, 'c1_status': c1_status, 'bins': {b: status for b in s['bins']}})
    return {'schema': 'rvw.mmu-check/1', 'model': model, 'manifest_sha256': digest(directory / 'manifest.json'),
            'status': 'fail' if any(r['status'] == 'fail' for r in rows) else 'pass' if rows and all(r['status'] == 'pass' for r in rows) else 'inconclusive',
            'scenarios': rows}


def report(directory, results, checked=None, protocol_config=None):
    """Report the scenario denominator. Never infer coverage from an ELF or bus activity."""
    from rvw.results import load_run
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    oracle = json.loads(Path(checked).read_text()) if checked else None
    if oracle and (oracle.get('schema') != 'rvw.mmu-check/1' or oracle.get('manifest_sha256') != digest(directory / 'manifest.json')):
        raise ValueError('coverage needs an rvw.mmu-check/1 report')
    checks = oracle['scenarios'] if oracle else []
    runs = [load_run(p) for p in run_paths_under(results)]
    rows = []
    for s in manifest['scenarios']:
        if digest(directory / s['elf']) != s['elf_sha256']:
            raise ValueError('ELF differs from build manifest')
        matches = [c for c in checks if c['id'] == s['id'] and c['elf_sha256'] == s['elf_sha256']]
        status = matches[0]['status'] if len(matches) == 1 else 'inconclusive'
        observed = {'status': 'inconclusive', 'reason': 'missing unique C1 observation file'}
        candidates = [r for r in runs if r.elf_sha256 == s['elf_sha256']]
        if len(candidates) != 1 or len(matches) != 1 or matches[0].get('c1_sha256') != digest(candidates[0].path / 'result.json'):
            status = 'inconclusive'
        if len(candidates) == 1:
            run = candidates[0]
            raw = json.loads((run.path / 'result.json').read_text())
            name = raw.get('details', {}).get('mmu_observations')
            if name and (run.path / name).is_file():
                path = run.path / name
                events = [json.loads(line) for line in path.read_text().splitlines()]
                if (not events or events[0].get('schema') != 'rvw.mmu-observations/1'
                        or events[0].get('elf_sha256') != s['elf_sha256']):
                    raise ValueError('invalid observation header')
                from .mmu_observe import check_walk, check_pma
                from .mmu_protocol import configured_check
                identity = events[0].get('identity', {})
                from .mmu_walk import same_run
                bound = same_run(identity, raw)
                unbound = dict(status='inconclusive', reason='observation identity is not bound to C1')
                # Keep bounded walk consistency separate from architectural coverage.
                observed = dict(status='recorded', path=str(path), sha256=digest(path),
                    c1_sha256=digest(run.path / 'result.json'),
                    walk_check=check_walk(s, events[1:]) if bound else unbound,
                    pma_check=check_pma(s, events[1:], (manifest.get("pma") or {}).get("regions")) if bound else unbound,
                    protocol_check=configured_check(events[1:], protocol_config) if bound else unbound,
                    counts={k: sum(e.get('kind') == k for e in events[1:])
                            for k in ('walk_request', 'walk_response', 'walk_retry', 'bus_a', 'memory_read')
                            if k in ('walk_request', 'walk_response', 'bus_a') or any(e.get('kind') == k for e in events[1:])})
            from .mmu_walk import check_c2, scenario_accesses
            trace_name = run.artifacts.get('rvfi_trace')
            if trace_name and (run.path / trace_name).is_file():
                observed['c2_walk_check'] = check_c2(run.path / trace_name, scenario_accesses(s), raw)
                if s.get('guest'):
                    from .mmu_nested import check_c2 as check_nested_c2
                    source_path = directory / (s['id'] + '.S')
                    if source_path.is_file() and digest(source_path) == s.get('source_sha256'):
                        observed['nested_walk_check'] = check_nested_c2(run.path / trace_name, s, raw, source_path.read_text())
                    else:
                        observed['nested_walk_check'] = dict(status='inconclusive', reason='missing hash-bound generated source')
        rows.append(dict(id=s['id'], elf_sha256=s['elf_sha256'], status=status,
                         bins=s['bins'], observations=observed))
    universe = sorted({b for s in rows for b in s['bins']})
    bins = {b: ('pass' if all(s['status'] == 'pass' for s in rows if b in s['bins']) else
                'fail' if any(s['status'] == 'fail' for s in rows if b in s['bins']) else 'inconclusive')
            for b in universe}
    return dict(schema='rvw.mmu-coverage/1', status='reported',
        manifest_sha256=digest(directory / 'manifest.json'),
        check_sha256=digest(checked) if checked else None,
        denominator=len(bins), counts={k: list(bins.values()).count(k) for k in ('pass', 'fail', 'inconclusive')},
        bins=bins, scenarios=rows,
        unverified=['walk request/response correctness', 'TLB request and completion protocol',
                    'A/D atomicity', 'concurrent PTE changes', 'cross-hart shootdowns',
                    'PMA width, boundary, atomic and conflicting-attribute behavior',
                    'device side effects', 'TW-clear interrupt wakeup'])


def register(sub):
    parser = sub.add_parser('mmu', help='build declarative Sv39 suites or validate them on Spike')
    actions = parser.add_subparsers(dest='mmu_action', required=True)
    b = actions.add_parser('build')
    b.add_argument('description', type=Path)
    b.add_argument('--out', required=True, type=Path)
    b.add_argument('--pma', type=Path, help='core-owned PMA declaration; recorded, not device coverage')
    b.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    r = actions.add_parser('reference')
    r.add_argument('directory', type=Path)
    r.add_argument('--spike', default='spike')
    r.add_argument('--timeout', type=float, default=10)
    c = actions.add_parser('check')
    c.add_argument('directory', type=Path)
    c.add_argument('--results', type=Path, required=True)
    c.add_argument('--platform', type=Path, required=True)
    c.add_argument('--model', choices=('spike', 'sail'), default='spike')
    c.add_argument('--timeout', type=float, default=120)
    c.add_argument('--sail')
    coverage = actions.add_parser('report', help='scenario bins and separate observation inventory')
    coverage.add_argument('directory', type=Path)
    coverage.add_argument('--results', type=Path, required=True)
    coverage.add_argument('--checked', type=Path)
    coverage.add_argument('--protocol-config', type=Path, help='project translation probe and memory-type policy')
    iommu = actions.add_parser('iommu', help='check decoded IOMMU scenarios against device observations')
    iommu.add_argument('description', type=Path, nargs='?')
    iommu.add_argument('--generate', action='store_true')
    iommu.add_argument('--seed', type=int, default=1)
    iommu.add_argument('--mode', choices=('sv39', 'sv48', 'sv57'), default='sv39')
    iommu.add_argument('--observations', type=Path)
    iommu.add_argument('--result', type=Path, help='C1 result that binds device observations')
    for p in (b, r, c, coverage, iommu):
        p.add_argument('--json', action='store_true')
        p.set_defaults(func=main)


def main(args):
    import math
    try:
        if args.mmu_action in ('reference', 'check') and (not math.isfinite(args.timeout) or args.timeout <= 0):
            raise ValueError('timeout must be finite and positive')
        if args.mmu_action == 'iommu':
            from .mmu_iommu import run as iommu_run, generate
            if args.generate:
                result = dict(generate(args.seed, args.mode), status='generated')
            elif args.description is None:
                raise ValueError('IOMMU comparison requires a description')
            else:
                result = iommu_run(args.description, args.observations, args.result)
        elif args.mmu_action == 'build':
            result = build(args.description, args.out, args.gcc, args.pma)
        elif args.mmu_action == 'reference':
            result = reference(args.directory, args.spike, args.timeout)
        elif args.mmu_action == 'report':
            result = report(args.directory, args.results, args.checked, args.protocol_config)
        else:
            result = check(args.directory, args.results, args.platform, args.model, args.timeout, args.sail)
        print(json.dumps(result, allow_nan=False))
        return 0 if result.get('status', 'pass') in ('pass', 'reported', 'consistent', 'generated') else 3 if result.get('status') == 'inconclusive' else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'error', 'message': str(exc)}))
        return 2
