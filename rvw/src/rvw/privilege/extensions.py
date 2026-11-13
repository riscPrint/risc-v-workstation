"""Pinned RV64 Sstc, state-enable, environment and landing-pad cases."""
from .programs import HEAD, TAIL
from .disabled import enter

PIN = 'https://docs.riscv.org/reference/isa/v20260120/'


def access(mode, setup, operation, denied=False, cause=2, tval=None):
    if mode == 'VS':
        setup += ' li t0, 1\n slli t0, t0, 39\n csrs mstatus, t0\n'
    code = HEAD + ' la t0, handler\n csrw mtvec, t0\n' + setup + enter('S' if mode == 'VS' else mode)
    code += 'access_site:\n ' + operation + '\necall_site:\n ecall\n j fail\nhandler:\n'
    code += f''' csrr t0, mcause
 li t1, {cause if denied else dict(M=11, S=9, U=8, VS=10)[mode]}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'fault_site' if denied and cause == 18 else 'access_site' if denied else 'ecall_site'}
 bne t0, t1, fail
'''
    if denied and tval is not None:
        code += f' csrr t0, mtval\n li t1, {tval}\n bne t0, t1, fail\n'
    return code + ' j pass\n' + TAIL


def row(name, code, spec):
    return dict(id=name, family=name.split('-')[0], bins=[name], assembly=code, spec=PIN + spec)


def programs(config):
    kind = config['kind']; isa = config['isa']; rows = []
    required = {'sstc': 'sstc', 'stateen': 'smstateen', 'envcfg': 'zicsr', 'landing': 'zicfilp'}[kind]
    if required not in isa:
        raise ValueError(f'{kind} requires {required} in isa')
    if kind == 'sstc':
        if 'zicntr' not in isa:
            raise ValueError('Sstc reference requires Zicntr time support')
        for mode in ('M', 'S', 'U'):
            for stce in (0, 1):
                for tm in (0, 1):
                    setup = f''' li t0, {stce << 63}
 csrw 0x30a, t0
 li t0, {tm << 1}
 csrw mcounteren, t0
'''
                    denied = mode == 'U' or (mode == 'S' and not (stce and tm))
                    code = access(mode, setup, 'csrr a0, 0x14d', denied)
                    rows.append(row(f'sstc-access-{mode.lower()}-{stce}-{tm}', code, 'priv/sstc.html'))
        # Event timing comes from STIP transitions, not synchronized time reads.
        code = HEAD + ''' li t0, 1
 slli t0, t0, 63
 csrs 0x30a, t0
 csrw 0x14d, zero
 li s0, 10000
1: csrr t0, mip
 andi t0, t0, 32
 bnez t0, 2f
 addi s0, s0, -1
 bnez s0, 1b
 j fail
2: li t0, -1
 csrw 0x14d, t0
 li s0, 10000
3: csrr t0, mip
 andi t0, t0, 32
 beqz t0, pass
 addi s0, s0, -1
 bnez s0, 3b
 j fail
''' + TAIL
        rows.append(row('sstc-pending-clear', code, 'priv/sstc.html'))
    elif kind == 'stateen':
        for mode in ('M', 'S', 'U'):
            for enabled in (0, 1):
                setup = f' li t0, {enabled << 63}\n csrw 0x30c, t0\n'
                rows.append(row(f'stateen-{mode.lower()}-{enabled}',
                    access(mode, setup, 'csrr a0, 0x10c', mode == 'U' or (mode == 'S' and not enabled)),
                    'priv/smstateen.html'))
    elif kind == 'envcfg':
        mask = config['envcfg']['implemented_mask']
        if type(mask) is not int or not 0 < mask < 1 << 64:
            raise ValueError('implemented_mask must be a positive 64-bit value')
        for mode, csr in [('M', '0x30a'), ('S', '0x10a'), ('U', '0x10a')]:
            for enabled in (0, 1):
                value = mask if enabled else 0
                operation = f'''csrw {csr}, a1
 csrr t1, {csr}
 li t0, {mask}
 and t1, t1, t0
 li t0, {value}
 bne t0, t1, fail'''
                rows.append(row(f'envcfg-{mode.lower()}-{enabled}', access(mode, f' li a1, {value}\n', operation, mode == 'U'), 'priv/machine.html'))
    elif kind == 'landing':
        for mode in ('S', 'U'):
            for enabled in (0, 1):
                for valid in (0, 1):
                    setup = f''' li t0, {enabled << 2}
 csrw 0x30a, t0
 csrw 0x10a, t0
'''
                    operation = f'''la a0, fault_site
 jr a0
 .balign 4
fault_site:
 {'.word 0x17' if valid else 'nop'}'''
                    rows.append(row(f'landing-{mode.lower()}-{enabled}-{valid}',
                        access(mode, setup, operation, bool(enabled and not valid), cause=18, tval=2), 'priv/priv-cfi.html'))
    if kind == 'sstc' and config.get('sstc',{}).get('virtualization'):
        if 'h' not in isa.split('_')[0][4:]:raise ValueError('virtual Sstc requires H')
        for stce in (0,1):
            for tm in (0,1):
                for hstce in (0,1):
                    for htm in (0,1):
                        setup=f' li t0, {stce<<63}\n csrw 0x30a, t0\n li t0, {tm<<1}\n csrw mcounteren, t0\n li t0, {hstce<<63}\n csrw 0x60a, t0\n li t0, {htm<<1}\n csrw 0x606, t0\n'
                        denied=not(stce and tm and hstce and htm)
                        cause=2 if not(stce and tm) else 22
                        rows.append(row(f'sstc-vs-{stce}-{tm}-{hstce}-{htm}',
                            access('VS',setup,'csrr a0, 0x14d',denied,cause=cause),'priv/sstc.html'))
    if kind == 'envcfg' and config['envcfg'].get('henvcfg_mask'):
        mask=config['envcfg']['henvcfg_mask']
        if 'h' not in isa.split('_')[0][4:]:raise ValueError('henvcfg requires H')
        for mode in ('M','S','U'):
            for enabled in (0,1):
                value=mask if enabled else 0
                operation=f'csrw 0x60a, a1\n csrr t1, 0x60a\n li t0, {mask}\n and t1, t1, t0\n li t0, {value}\n bne t0, t1, fail'
                rows.append(row(f'envcfg-h-{mode.lower()}-{enabled}',access(mode,f' li a1, {value}\n',operation,mode=='U'),'priv/hypervisor.html'))
    if kind == 'landing':
        for mode in ('S','U'):
            for label in (0x12345,0x12346):
                setup=' li t0, 4\n csrw 0x30a, t0\n csrw 0x10a, t0\n li t2, 0x12345000\n'
                operation=f'la a0, fault_site\n jr a0\n .balign 4\nfault_site:\n .word {(label<<12)|0x17}'
                rows.append(row(f'landing-label-{mode.lower()}-{label:x}',
                    access(mode,setup,operation,label!=0x12345,cause=18,tval=2),'priv/priv-cfi.html'))
    return rows
