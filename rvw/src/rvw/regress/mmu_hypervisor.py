"""Project-selected VS/G geometries and explicit hypervisor data operations."""


def assembly(s):
    if s.get('guest_op', '').startswith('vs-'):
        return virtual_assembly(s)
    from .mmu import ROOT, DATA, FLAGS
    from .mmu_paging import MODES, page_tables
    vs = MODES[s['mode']]
    g = MODES[s.get('guest_mode', 'sv39')]
    tables, leaf = page_tables(s, ROOT, DATA, sum(FLAGS[f] for f in set(s['flags'])))
    root = 0x80020000
    gt = [[0] * 2048] + [[0] * 512 for _ in range(g.levels - 2)]
    addresses = [root] + [root + 16384 + i * 4096 for i in range(g.levels - 2)]
    for depth in range(g.levels - 2):
        level = g.levels - depth - 1
        index = DATA >> (12 + 9 * level) & (2047 if depth == 0 else 511)
        gt[depth][index] = (addresses[depth + 1] >> 12 << 10) | 1
    gt[-1][0] = (0x80000000 >> 12 << 10) | 0xdf
    gt[-1][1] = (DATA >> 12 << 10) | sum(FLAGS[f] for f in set(s['guest_flags']))
    op = s.get('guest_op', 'hlv.d')
    store = op == 'hsv.d'
    fault = s['expect'] != 'success'
    cause = (23 if store else 21) if s.get('guest_fault') else (15 if store else 13)
    access = f'{op} a0, (t3)' if not store else 'hsv.d a0, (t3)'
    code = f'''.option norvc
.section .text
.globl _start
_start:
 csrr t0, mhartid
 bnez t0, park
 la t0, trap
 csrw mtvec, t0
 csrw mie, zero
 csrw medeleg, zero
 csrw mideleg, zero
 li t0, -1
 csrw pmpaddr0, t0
 li t0, 15
 csrw pmpcfg0, t0
 li t0, 256
 csrw hstatus, t0
 li t0, {vs.satp(ROOT)}
 csrw vsatp, t0
 csrr t1, vsatp
 bne t0, t1, fail
 li t0, {(g.satp_mode << 60) | (s.get('vmid', 0) << 44) | (root >> 12)}
 csrw hgatp, t0
 csrr t1, hgatp
 bne t0, t1, fail
 {('li t0, 0x2000000000000000' + chr(10) + ' csrs menvcfg, t0' + chr(10) + ' csrs henvcfg, t0') if s.get('ad_mode') == 'hardware' else ('li t0, 0x2000000000000000' + chr(10) + ' csrc henvcfg, t0') if s.get('ad_mode') == 'svade' else ''}
 hfence.gvma x0, x0
 hfence.vvma x0, x0
 li t3, 0x40000000
 li a0, 43
access_site:
 {access}
 {'j fail' if fault else ''}
 {'li t0, ' + str(DATA) + chr(10) + ' ld a0, 0(t0)' if store else ''}
 li t1, {43 if store else 42}
 bne a0, t1, fail
 j {'check_ad' if 'ad_expect' in s else 'pass'}
trap:
 {'csrr t0, mcause' if fault else 'j fail'}
 li t1, {cause}
 bne t0, t1, fail
 csrr t0, mtval
 li t1, 0x40000000
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access_site
 bne t0, t1, fail
'''
    if s.get('guest_fault'):
        code += f' csrr t0, mtval2\n li t1, {DATA >> 2}\n bne t0, t1, fail\n'
    if s.get('guest_fault'):
        code += ''' csrr t0, mtinst
 beqz t0, tinst_ok
 la t1, access_site
 lw t1, 0(t1)
 li t2, -1015809
 and t1, t1, t2
 bne t0, t1, fail
tinst_ok:
'''
    if 'ad_expect' in s:
        expected = (DATA >> 12 << 10) | sum(FLAGS[f] for f in set(s['flags'])) | s['ad_expect']
        code += f' j check_ad\ncheck_ad:\n li t0, {leaf}\n ld t0, 0(t0)\n li t1, {expected}\n bne t0, t1, fail\n'
    code += '''pass:
 li t1, 1
 j finish
fail:
 li t1, 3
finish:
 la t0, tohost
 sd t1, 0(t0)
park:
 j park
.section .tohost,"aw"
.balign 64
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
.section .tables,"aw"
'''
    for table in tables:
        code += '\n'.join(f' .dword {p}' for p in table) + '\n'
    code += f' .zero {root - ROOT - len(tables) * 4096}\n'
    for table in gt:
        code += '\n'.join(f' .dword {p}' for p in table) + '\n'
    if s.get('guest_switch'):
        alternate = (addresses[-1] + 4096 + 16383) & -16384
        shift = alternate - root
        other = [list(t) for t in gt]
        for depth in range(len(other) - 1):
            level = g.levels - depth - 1
            index = DATA >> (12 + 9 * level) & (2047 if depth == 0 else 511)
            other[depth][index] = ((addresses[depth + 1] + shift) >> 12 << 10) | 1
        other[-1][1] = ((DATA + 2097152) >> 12 << 10) | sum(FLAGS[f] for f in set(s['guest_flags']))
        switch_code = ''
        for selected, value in ((alternate, 43), (root, 42)):
            hgatp = (g.satp_mode << 60) | (s.get('vmid', 0) << 44) | (selected >> 12)
            switch_code += f''' li t0, {hgatp}
 csrw hgatp, t0
 csrr t1, hgatp
 bne t0, t1, fail
 hfence.gvma x0, x0
 hfence.vvma x0, x0
 hlv.d a0, (t3)
 li t1, {value}
 bne a0, t1, fail
'''
        code = code.replace(' j pass\ntrap:', switch_code + ' j pass\ntrap:')
        code += f' .zero {alternate - addresses[-1] - 4096}\n'
        for table in other:
            code += '\n'.join(f' .dword {p}' for p in table) + '\n'
    code += '.section .data\n .dword 42\n'
    if s.get('guest_switch'):
        code += ' .zero 2097144\n .dword 43\n'
    if s.get('guest_trap') == 'hs':
        code = code.replace(' li t3, 0x40000000\n', ''' la t0, trap
 csrw stvec, t0
 li t0, 0xa0a000
 csrw medeleg, t0
 li t0, 0x1800
 csrc mstatus, t0
 li t0, 0x800
 csrs mstatus, t0
 la t0, access_site
 csrw mepc, t0
 li t3, 0x40000000
 mret
''')
        for m, h in [('mcause','scause'),('mtval2','htval'),('mtval','stval'),('mepc','sepc'),('mtinst','htinst')]:
            code = code.replace('csrr t0, ' + m, 'csrr t0, ' + h)
    return code


def virtual_assembly(s):
    op = s['guest_op']
    instruction = {'vs-satp': 0x18002573, 'vs-sfence': 0x12000073, 'vs-sret': 0x10200073}[op]
    code = assembly(dict(s, guest_op='hlv.d', flags='VRWXAD', expect='page-fault', guest_fault=False))
    code = code.replace(' li t0, 256\n csrw hstatus', f" li t0, {256 | (1 << (22 if op == 'vs-sret' else 20))}\n csrw hstatus")
    start = code.index(' li t3, 0x40000000\n')
    end = code.index('trap:\n', start)
    code = code[:start] + """ li t0, 0x8000000800
 csrs mstatus, t0
 li t0, 0x40000000
 csrw mepc, t0
 mret
""" + code[end:]
    code = code.replace(' li t1, 13\n', ' li t1, 22\n')
    code = code.replace(' csrr t0, mtval\n li t1, 0x40000000', f' csrr t0, mtval\n li t1, {instruction}')
    code = code.replace(' la t1, access_site', ' li t1, 0x40000000')
    return code.replace('.section .data\n .dword 42\n', f'.section .data\n .word {instruction}\n .word 0\n')


def matrix(config=None):
    if config is not None and (not isinstance(config, dict) or set(config) != {'modes'} or not config['modes'] or set(config['modes']) - {'sv39', 'sv48', 'sv57'}):
        raise ValueError('guest_matrix requires supported modes')
    cases = []
    for vs in ('sv39', 'sv48', 'sv57'):
        for g in ('sv39', 'sv48', 'sv57'):
            for op in ('hlv.d', 'hlvx.wu', 'hsv.d'):
                for fault in ('none', 'vs', 'g'):
                    store = op == 'hsv.d'
                    cases.append(dict(id=f'{vs}-{g}-{op.replace(".", "-")}-{fault}', mode=vs, guest=True,
                                      guest_mode=g, guest_op=op, guest_flags='VUAD' if fault == 'g' else 'VRWXUAD',
                                      flags='VAD' if fault == 'vs' else 'VRWXAD', guest_fault=fault == 'g', level=0,
                                      access='store' if store else 'load', expect='success' if fault == 'none' else 'page-fault',
                                      bins=[f'{vs}.{g}.{op}.{fault}']))
    for vs in ('sv39', 'sv48', 'sv57'):
        for ad in ('svade', 'hardware'):
            for op in ('hlv.d', 'hsv.d'):
                store = op == 'hsv.d'
                cases.append(dict(id=f'{vs}-{ad}-{op.replace(".", "-")}', mode=vs, guest=True, guest_mode='sv39',
                                  guest_op=op, guest_flags='VRWXUAD', flags='VRWX', level=0, access='store' if store else 'load',
                                  expect='success' if ad == 'hardware' else 'page-fault', ad_mode=ad,
                                  ad_expect=(192 if store else 64) if ad == 'hardware' else 0, bins=[f'{vs}.{ad}.{op}']))
    for op in ('vs-satp', 'vs-sfence', 'vs-sret'):
        cases.append(dict(id=op, mode='sv39', guest=True, guest_mode='sv39', guest_op=op,
                          guest_flags='VRWXUAD', flags='VRWXAD', level=0, access='load', expect='virtual-instruction', bins=[op]))
    for mode in ('sv39', 'sv48', 'sv57'):
        cases.append(dict(id=mode+'-g-root-reuse', mode=mode, guest=True, guest_mode=mode, guest_switch=True,
                          vmid=7, guest_flags='VRWXUAD', flags='VRWXAD', level=0, access='load', expect='success', bins=[mode+'.g-root-reuse']))
        cases.append(dict(id=mode+'-hs-guest-fault', mode=mode, guest=True, guest_mode=mode, guest_trap='hs', guest_fault=True,
                          guest_flags='VUAD', flags='VRWXAD', level=0, access='load', expect='page-fault', bins=[mode+'.htval']))
    return cases if config is None else [s for s in cases if s['mode'] in config['modes'] and s.get('guest_mode', 'sv39') in config['modes']]

