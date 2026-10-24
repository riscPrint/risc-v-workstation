module tb;
  reg clk=0;
  reg [3:0] a=0;
  reg choose=0;
  wire [4:0] y;
  tiny dut(.clk(clk), .a(a), .choose(choose), .y(y));
  integer i;
  initial begin
    for (i=0; i<8; i=i+1) begin
      a=i;
      #1;
      if (y !== (i ^ 3)) $fatal(1, "MISMATCH");
      clk=1; #1; clk=0;
    end
    $display("PASS");
    $finish;
  end
endmodule
