module top(input clk, input enable);
  reg [1:0] count=0;
  always @(posedge clk) begin
    if(enable) count <= count==2 ? 0 : count+1;
    assert(count!=3);
  end
endmodule
