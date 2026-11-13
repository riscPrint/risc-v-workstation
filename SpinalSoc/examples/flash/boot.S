.option norvc
.section .text
.global _start
_start:
  li s0,0x10000000
  sw zero,8(s0)               # Mode 0, active-low chip select.
  li t0,8
  sw t0,12(s0)
  li t0,2
  sw t0,16(s0)
  sw t0,20(s0)
  sw t0,24(s0)
  li a0,0x11000000
  call command
  li a0,3
  call command
  li a0,0
  call command
  li a0,1
  call command
  li a0,0                     # Flash offset 0x000100.
  call command
  li s1,0x80010000
  li s2,APP_SIZE
  li s3,0
copy:
  li a0,0x010000ff
  call command
response:
  lw t0,0(s0)
  bgez t0,response            # Nonblocking SPI FIFO valid bit is bit 31.
  andi t0,t0,255
  sb t0,0(s1)
  add s3,s3,t0
  addi s1,s1,1
  addi s2,s2,-1
  bnez s2,copy
  li a0,0x10000000
  call command
  li t0,APP_SUM
  bne s3,t0,bad_image
  fence rw,rw
  fence.i
  li t0,0x80010000
  jr t0
bad_image:
  li t0,0x10001000
  li t1,3
  sw t1,0(t0)
1: j 1b
command:
  lw t0,4(s0)
  srli t0,t0,16
  beqz t0,command
  sw a0,0(s0)
  ret
