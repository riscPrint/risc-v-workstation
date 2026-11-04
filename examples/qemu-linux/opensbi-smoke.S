/* Bounded startup fixture. This supplies no Linux DTB or device adapter. */
#ifndef FIRMWARE_IMAGE
#error Define FIRMWARE_IMAGE as the quoted absolute path to fw_jump.bin
#endif
.option norvc
.section .text.reset,"ax"
.globl _start
_start:
.irp reg,ra,sp,gp,tp,t0,t1,t2,s0,s1,a0,a1,a2,a3,a4,a5,a6,a7,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11,t3,t4,t5,t6
  addi \reg,zero,0
.endr
  lui t0,0x80200
  jalr zero,t0,0
.section .firmware,"ax"
.incbin FIRMWARE_IMAGE
