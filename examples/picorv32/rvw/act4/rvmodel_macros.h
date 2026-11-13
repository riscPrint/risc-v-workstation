/* CSR-free instruction bootstrap for the declared RV32IM platform. */
#define RVMODEL_BOOT
#define RVMODEL_BOOT_TO_MMODE
#define RVMODEL_DATA_SECTION .pushsection .tohost,"aw",@progbits; .balign 8; .global tohost; tohost: .dword 0; .global fromhost; fromhost: .dword 0; .popsection
#define RVMODEL_HALT_PASS li x1,1; la t0,tohost; sw x1,0(t0); sw x0,4(t0); 1: j 1b;
#define RVMODEL_HALT_FAIL li x1,3; la t0,tohost; sw x1,0(t0); sw x0,4(t0); 1: j 1b;
#define RVMODEL_IO_WRITE_STR(_R1,_R2,_R3,_STR_PTR)
#define RVMODEL_ACCESS_FAULT_ADDRESS 0
#define RVMODEL_INTERRUPT_LATENCY 1
#define RVMODEL_TIMER_INT_SOON_DELAY 5000
