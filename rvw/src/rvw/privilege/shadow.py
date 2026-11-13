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
    rows=[]
    for mode in ('S','U'):
        for kind in ('roundtrip','mismatch','readonly-recover','ordinary-page','bare','normal-store'):
            readonly=kind=='readonly-recover'
            leaf=0xc3 if readonly else 0xc7 if kind=='ordinary-page' else 0xc5
            leaf|=16 if mode=='U' else 0
            code=HEAD+''' la t0, handler
 csrw mtvec, t0
 li s0, 0
 li t0, 8
 csrs 0x30a, t0
 csrs 0x10a, t0
 li t0, 0x40001000
 csrw 0x11, t0
'''
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
            code+=enter(mode)+'''access_site:
 li ra, 42
push_site:
'''
            code+=' sd ra, 0(a0)\n' if kind=='normal-store' else ' sspush ra\n'
            if kind=='normal-store':code=code.replace('push_site:\n sd ra', ' li a0, 0x40000ff8\npush_site:\n sd ra')
            if kind=='mismatch':code+=' li ra, 43\n'
            code+='pop_site:\n sspopchk ra\n' if kind!='normal-store' else ''
            code+=''' csrr t0, 0x11
 li t1, 0x40001000
 bne t0, t1, fail
ecall_site:
 ecall
 j fail
handler:
 csrr t0, mcause
'''
            denied=kind in ('mismatch','ordinary-page','bare','normal-store')
            cause=18 if kind=='mismatch' else 7
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
 mret
completed:
 csrr t0, mcause
'''
            code+=f''' li t1, {cause if denied else 9 if mode=='S' else 8}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'pop_site' if kind=='mismatch' else 'push_site' if denied else 'ecall_site'}
 bne t0, t1, fail
'''
            if kind=='mismatch':code+=' csrr t0, mtval\n li t1, 3\n bne t0, t1, fail\n'
            code+=' j pass\n'+TAIL+'''.section .data
.balign 4096
root: .space 4096
middle: .space 4096
leaves: .space 4096
shadow_page: .space 4096
'''
            rows.append(dict(id=f'shadow-{mode.lower()}-{kind}',family='shadow',assembly=code,
                bins=[f'shadow.{mode}.{kind}'],spec='https://docs.riscv.org/reference/isa/v20260120/priv/priv-cfi.html'))
    return rows
