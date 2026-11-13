"""RV32 Sstc low/high CSR access, compare updates and virtual-time events."""
from .programs import HEAD,TAIL
from .disabled import enter

HEAD32=HEAD
TAIL32=TAIL.replace(' sd t1, 0(t0)',' sw t1, 0(t0)\n sw zero, 4(t0)')
SPEC='https://docs.riscv.org/reference/isa/v20260120/priv/sstc.html'


def setup(stce,tm,hstce=None,htm=None):
    code=f' li t0, {stce<<31}\n csrw 0x31a, t0\n li t0, {tm<<1}\n csrw mcounteren, t0\n'
    if hstce is not None:
        code+=f' li t0, {hstce<<31}\n csrw 0x61a, t0\n li t0, {htm<<1}\n csrw 0x606, t0\n'
    return code


def access(mode,stce,tm,csr,hstce=None,htm=None):
    virtual=mode=='VS'
    denied=(not(stce and tm and hstce and htm) if virtual else mode=='U' or (mode=='S' and not(stce and tm)))
    cause=(2 if not(stce and tm) else 22) if virtual else 2
    code=HEAD32+' la t0, handler\n csrw mtvec, t0\n'+setup(stce,tm,hstce,htm)
    if virtual:code+=' li t0, 128\n csrs 0x310, t0\n'
    code+=enter('S' if virtual else mode)+f'''access_site:
 csrr a0, {csr:#x}
ecall_site:
 ecall
 j fail
handler:
 csrr t0, mcause
 li t1, {cause if denied else dict(M=11,S=9,U=8,VS=10)[mode]}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'access_site' if denied else 'ecall_site'}
 bne t0, t1, fail
 j pass
'''+TAIL32
    return code


def pending(virtual=False):
    from .timer_pending import program
    return program(32,virtual)


def programs(config):
    isa=config.get('isa','')
    if not isa.startswith('rv32') or 'sstc' not in isa or 'zicntr' not in isa:
        raise ValueError('RV32 timer campaigns need RV32, Sstc and Zicntr')
    rows=[]
    for mode in ('M','S','U'):
        for stce in (0,1):
            for tm in (0,1):
                for csr in (0x14d,0x15d):
                    name=f'sstc32-{mode.lower()}-{stce}-{tm}-{csr:x}'
                    rows.append(dict(id=name,assembly=access(mode,stce,tm,csr)))
    rows.append(dict(id='sstc32-pending',assembly=pending()))
    code=HEAD32+setup(1,1)+''' li t0, -1
 csrw 0x14d, t0
 li t0, 0x12345678
 csrw 0x15d, t0
 li t0, 0x9abcdef0
 csrw 0x14d, t0
 csrr t1, 0x14d
 bne t0, t1, fail
 li t0, 0x12345678
 csrr t1, 0x15d
 bne t0, t1, fail
 li t0, -1
 csrw 0x14d, t0
 csrw 0x15d, t0
 csrw 0x14d, t0
 j pass
'''+TAIL32
    rows.append(dict(id='sstc32-split-readback',assembly=code))
    if config.get('sstc',{}).get('virtualization'):
        if 'h' not in isa.split('_')[0][4:]:raise ValueError('virtual timer requires H')
        for stce in (0,1):
            for tm in (0,1):
                for hstce in (0,1):
                    for htm in (0,1):
                        for csr in (0x14d,0x15d):
                            name=f'sstc32-vs-{stce}-{tm}-{hstce}-{htm}-{csr:x}'
                            rows.append(dict(id=name,assembly=access('VS',stce,tm,csr,hstce,htm)))
        rows.append(dict(id='sstc32-virtual-pending',assembly=pending(True)))
    from .timer_pending import contract
    for row in rows:
        row.update(family='sstc',bins=[row['id']],spec=SPEC)
        if 'pending' in row['id']:
            row['timer_contract']=contract(config,'virtual' in row['id'])
        if 'h' in isa.split('_')[0][4:]:
            row['assembly']=row['assembly'].replace(HEAD32,HEAD32+' li t0, 128\n csrc 0x310, t0\n',1)
    return rows
