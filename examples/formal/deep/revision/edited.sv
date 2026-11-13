module top(input clk, input enable, output reg [7:0] unrelated=0);
  reg [1:0] count=0;
  always @(posedge clk) begin
    unrelated <= unrelated+1;
    if(enable) count <= count==2 ? 0 : count+1;
    assert(count!=3);
  end
endmodule
