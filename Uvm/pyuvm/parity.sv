module parity(
 input logic clk, write_enable,
 input logic [1:0] address,
 input logic [31:0] write_data,
 output logic [31:0] read_data
);
 logic [31:0] memory [0:3];
 always_ff @(posedge clk) if(write_enable) memory[address] <= write_data;
 assign read_data=memory[address];
endmodule
