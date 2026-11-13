"""Zicfiss programs and an independent expected stack model."""
from .programs import HEAD, TAIL
from .disabled import enter


class Stack:
    def __init__(self, pointer, memory=None):
        self.pointer=pointer;self.memory={} if memory is None else dict(memory)

    def push(self,value):
        if self.pointer%8:raise ValueError('access fault')
        self.memory[self.pointer-8]=value;self.pointer-=8

    def pop(self,value):
        if self.pointer%8:raise ValueError('access fault')
        if self.memory.get(self.pointer)!=value:raise ValueError('software check')
        self.pointer+=8


def programs(config):
    if 'zicfiss' not in config.get('isa',''):raise ValueError('shadow campaign requires Zicfiss')
    return [_program(mode, kind, register) for mode in ('S','U')
            for kind in ('roundtrip','mismatch','readonly-recover','ordinary-page','bare',
                         'normal-store','normal-load','fetch','misaligned-push',
                         'misaligned-pop','guard-overflow','guard-underflow')
            for register in ('ra','t0')]


def _program(mode, kind, register):
    readonly=kind=='readonly-recover'
    leaf=0xc3 if readonly else 0xc7 if kind=='ordinary-page' else 0xc5
    leaf|=16 if mode=='U' else 0
    pointer={'misaligned-push':0x40001004,'misaligned-pop':0x40000ffc,
             'guard-overflow':0x40000000}.get(kind,0x40001000)
    code=HEAD+f''' la t0, handler
 csrw mtvec, t0
 li s0, 0
 li t0, 8
 csrs 0x30a, t0
 csrs 0x10a, t0
 li t0, {pointer}
 csrw 0x11, t0
 csrr s4, 0x11
'''
    if kind.startswith('misaligned-'):
        code+=' andi t1, s4, 7\n bnez t1, pointer_ready\n andi t0, t0, -8\n bne s4, t0, fail\npointer_ready:\n'
    if kind!='bare':
        code+=f''' la t0, root
 li t1, {0x200000cf | (16 if mode=='U' else 0)}
 sd t1, 16(t0)
 la t1, middle
 srli t1, t1, 2
 ori t1, t1, 1
 sd t1, 8(t0)
 la t0, middle
 la t1, leaves
 srli t1, t1, 2
 ori t1, t1, 1
 sd t1, 0(t0)
 la t0, leaves
 la t1, shadow_page
 srli t1, t1, 2
 ori t1, t1, {leaf}
 sd t1, 0(t0)
 la t0, root
 srli t0, t0, 12
 li t1, 8
 slli t1, t1, 60
 or t0, t0, t1
 csrw satp, t0
 sfence.vma
'''
    code+=enter(mode)+f'access_site:\n li {register}, 42\npush_site:\n'
    if kind=='normal-store':code=code.replace('push_site:\n',' li a0, 0x40000ff8\npush_site:\n');code+=' sd '+register+', 0(a0)\n'
    elif kind=='fetch':code+=' li a0, 0x40000000\n jr a0\n'
    elif kind not in ('misaligned-pop','guard-underflow'):code+=' sspush '+register+'\n'
    if kind=='normal-load':
        code+=' li a0, 0x40000ff8\n ld a1, 0(a0)\n li a2, 42\n bne a1, a2, fail\n'
    if kind=='mismatch':code+=' li '+register+', 43\n'
    if kind not in ('normal-store','fetch'):
        code+='pop_site:\n sspopchk '+register+'\n'
    code+=""" csrr t0, 0x11
 li t1, 0x40001000
 bne t0, t1, fail
ecall_site:
 ecall
 j fail
handler:
 mv s5, t0
 csrr t0, mcause
"""
    denied=kind in ('mismatch','ordinary-page','bare','normal-store','fetch',
                    'misaligned-push','misaligned-pop','guard-overflow','guard-underflow')
    cause=18 if kind=='mismatch' else 1 if kind=='fetch' else 15 if kind.startswith('guard-') else 7
    if readonly:
        code+=f''' bnez s0, completed
 li t1, 15
 bne t0, t1, fail
 csrr t0, mepc
 la t1, push_site
 bne t0, t1, fail
 csrr t0, 0x11
 li t1, 0x40001000
 bne t0, t1, fail
 la t0, leaves
 ld t1, 0(t0)
 li t2, -8
 and t1, t1, t2
 ori t1, t1, 5
 sd t1, 0(t0)
 sfence.vma
 li s0, 1
 mv t0, s5
 mret
completed:
 csrr t0, mcause
'''
    if kind.startswith('misaligned-'):
        code+=f''' andi t1, s4, 7
 bnez t1, unaligned_fault
 li t1, {9 if mode=='S' else 8}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, ecall_site
 bne t0, t1, fail
 j pass
unaligned_fault:
'''
    code+=f''' li t1, {cause if denied else 9 if mode=='S' else 8}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'pop_site' if kind in ('mismatch','misaligned-pop','guard-underflow') else 'fetch_site' if kind=='fetch' else 'push_site' if denied else 'ecall_site'}
 bne t0, t1, fail
'''
    if kind=='fetch':code=code.replace('la t1, fetch_site','li t1, 0x40000000')
    if denied:
        expected_pointer=0x40000ff8 if kind=='mismatch' else pointer
        code+=f' csrr t0, 0x11\n li t1, {expected_pointer}\n bne t0, t1, fail\n'
    if kind=='mismatch':code+=' csrr t0, mtval\n li t1, 3\n bne t0, t1, fail\n'
    code+=' j pass\n'+TAIL+'''.section .data
.balign 4096
root: .space 4096
middle: .space 4096
leaves: .space 4096
shadow_page: .space 4088
 .dword 42
'''
    return dict(id=f'shadow-{mode.lower()}-{kind}-{register}',family='shadow',assembly=code,
        bins=[f'shadow.{mode}.{kind}.{register}'],spec='https://docs.riscv.org/reference/isa/v20260120/priv/priv-cfi.html')
