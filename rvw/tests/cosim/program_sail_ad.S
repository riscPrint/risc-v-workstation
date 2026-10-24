.option norvc
.section .text
.globl _start
_start:
 la t0, handler
 csrw mtvec,t0
 la t0, root
 srli t0,t0,12
 li t1,0x8000000000000000
 or t0,t0,t1
 csrw satp,t0
 sfence.vma
 li t0,0x2000000000000000
 csrs menvcfg,t0
 li t0,0x1800
 csrc mstatus,t0
 li t0,0x20800
 csrs mstatus,t0
 li t0,0x2010
load_site:
 lw a0,0(t0)
 li t0,0x20000
 csrc mstatus,t0
 li t1,1
 j finish
.balign 4
handler:
 li t0,0x20000
 csrc mstatus,t0
 li t1,3
finish:
 la t0,tohost
 sd t1,0(t0)
1:j 1b
.section .data
.balign 4096
root:
 .dword 0x20000007
 .zero 4088
.balign 4096
data:
 .zero 16
 .word 42
.balign 8
.globl tohost
tohost:.dword 0
