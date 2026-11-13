module rvfi_wrapper(input clock, input reset, `RVFI_OUTPUTS);
  // Unconstrained RAM data: instruction checks only, no memory-system proof.
  (* anyseq *) reg [31:0] instruction;
  (* anyseq *) reg [31:0] load_data;
  Core dut (
    .clk(clock), .reset(reset), .io_boot(32'h80000000),
    .io_instruction(instruction), .io_loadData(load_data),
    @RVFI_CONNECTIONS@
  );
endmodule
