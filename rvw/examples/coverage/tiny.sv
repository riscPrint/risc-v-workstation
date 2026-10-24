module tiny(input logic clk, input logic [3:0] a, input logic choose, output logic [4:0] y);
  reg [1:0] state = 0;
  always @(posedge clk)
    if (state == 2) state <= 0;
    else state <= state + 1;
  always_comb begin
    if (choose) y = {1'b0, a} + 5'd1;
    else y = {1'b0, a} ^ 5'd3;
    if (a == 4'd15) y = 0;
    if (state == 3) y = 5'd31;
  end
endmodule
