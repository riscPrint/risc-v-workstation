// Project wrappers map protocol agents and core pins to these observations.
interface rvw_cpu_if(input bit clk);
 bit reset_n;
 bit [31:0] irq;
 bit debug_req;
 bit rvfi_valid;
 bit state_valid;
 longint unsigned gpr_state[32], csr_addresses[8], csr_values[8];
 int unsigned csr_count;
 longint unsigned rvfi_order;
 // pc, next PC, instruction, mode, rd, rd value, memory address, read mask,
 // write mask, read data, write data, trap, memory fault, rs1, rs1 data,
 // rs2, rs2 data, interrupt, halt. Matches the strict Spike DPI bridge.
 longint unsigned retirement[19];
endinterface
