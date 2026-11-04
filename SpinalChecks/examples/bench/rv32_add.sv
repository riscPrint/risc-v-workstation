// Handwritten RISC-V arithmetic block fixture. The widened sum is the oracle.
module rv32_add(input clk, reset, input [31:0] a, b);
 wire [31:0] dut_sum = a + b;
 wire [32:0] reference_sum = {1'b0, a} + {1'b0, b};
 always @(posedge clk) if (!reset) assert(dut_sum == reference_sum[31:0]);
endmodule
