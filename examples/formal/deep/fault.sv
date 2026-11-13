module fault(input clk);
  reg [3:0] count = 0;
  always @(posedge clk) begin
    count <= count + 1;
    assert(count <= 9);
  end
endmodule
