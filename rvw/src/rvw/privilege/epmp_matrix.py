"""Complete Smepmp 1.0 MML permission table, separate from standard PMP."""
from .programs import HEAD, TAIL
from .disabled import enter

# Index is the ordinary R/W/X field value. Values are effective R/W/X masks.
UNLOCKED = [(0,0),(0,1),(3,1),(0,3),(0,4),(0,5),(3,3),(0,7)]
LOCKED = [(0,0),(1,0),(4,4),(3,0),(4,0),(5,0),(5,4),(1,1)]
SPEC='https://docs.riscv.org/reference/isa/v20260120/priv/smepmp.html'


def permission(locked, rwx, mode):
    if rwx not in range(8) or mode not in ('M','S','U','mprv-s','mprv-u'):
        raise ValueError('invalid Smepmp permission query')
    return (LOCKED if locked else UNLOCKED)[rwx][0 if mode=='M' else 1]


def programs(config):
    if 'smepmp' not in config.get('isa',''):raise ValueError('Smepmp matrix needs Smepmp')
    if config.get('epmp',{}).get('rlb_supported') is not True:
        raise ValueError('MML bootstrap requires declared RLB support')
    rows=[]
    for locked in (False,True):
        for rwx in range(8):
            for mode in ('M','S','U','mprv-s','mprv-u'):
                for access,bit in [('read',1),('write',2),('execute',4)]:
                    if mode.startswith('mprv') and access=='execute':continue
                    allowed=bool(permission(locked,rwx,mode)&bit)
                    cfg=0x18|rwx|(0x80 if locked else 0)
                    physical='M' if mode.startswith('mprv') else mode
                    code=HEAD+''' csrw pmpcfg0, zero
 la t0, handler
 csrw mtvec, t0
 li t0, 4
 csrw 0x747, t0
 li t0, 0x200001ff
 csrw pmpaddr0, t0
 li t0, 0x200007ff
 csrw pmpaddr1, t0
 la t0, test_area
 srli t0, t0, 2
 ori t0, t0, 1
 csrw pmpaddr2, t0
 li t0, 0x9b9d
 csrw pmpcfg0, t0
 li t0, 5
 csrw 0x747, t0
'''+f''' li t0, {0x1e9e | (cfg<<16)}
 csrw pmpcfg0, t0
 li t0, 1
 csrw 0x747, t0
 csrr t0, 0x747
 andi t0, t0, 5
 li t1, 1
 bne t0, t1, fail
 csrr t0, pmpcfg0
 srli t0, t0, 16
 andi t0, t0, 255
 li t1, {cfg}
 bne t0, t1, fail
'''+enter(physical)
                    code+='access_site:\n'
                    if mode.startswith('mprv'):
                        code+=f''' li t0, 0x1800
 csrc mstatus, t0
 li t0, {0x20000 | (0x800 if mode=='mprv-s' else 0)}
 csrs mstatus, t0
'''
                    code+=' la a0, test_area\n li a1, 43\naccess_op:\n'
                    if access=='read':code+=' lw a1, 0(a0)\n li t0, 42\n bne a1, t0, fail\n'
                    elif access=='write':code+=' sw a1, 0(a0)\n lw t0, 0(a0)\n bne a1, t0, fail\n'
                    else:code+=' jr a0\n'
                    cause=({'M':11,'S':9,'U':8}[physical] if allowed else {'read':5,'write':7,'execute':1}[access])
                    code+=f'''after_access:
ecall_site:
 ecall
 j fail
handler:
 csrr t0, mcause
 li t1, {cause}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'ecall_site' if allowed else 'test_area' if access=='execute' else 'access_op'}
 bne t0, t1, fail
 j pass
'''+TAIL+'''.section .probe,"awx"
.balign 16
test_area:
'''+(' j after_access\n .word 0\n' if access=='execute' else ' .word 42, 0\n')+' .dword 0\n'
                    name=f'epmp-mml-{int(locked)}-{rwx}-{mode}-{access}'
                    rows.append(dict(id=name,family='epmp',assembly=code,spec=SPEC,
                        bins=[f'epmp.mml.{int(locked)}.{rwx}.{mode}.{access}'],
                        expected_allowed=allowed,link_options=['-Wl,--section-start=.probe=0x80008000']))
    return rows
