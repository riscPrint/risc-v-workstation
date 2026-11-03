module tb;
  reg [0:0] dw = 1;
  reg [4:0] fn = 0;
  reg [63:0] a = 0, b = 0;
  wire [63:0] y, adder;
  wire cmp;
  reg [63:0] expected;
  integer i, j, op;
  reg [63:0] vectors [0:7];
  RocketALU dut(.io_dw(dw), .io_fn(fn), .io_in1(a), .io_in2(b),
                .io_out(y), .io_adder_out(adder), .io_cmp_out(cmp));
  initial begin
    vectors[0]=0; vectors[1]=1; vectors[2]=2; vectors[3]=15;
    vectors[4]=64'hffffffffffffffff; vectors[5]=64'h8000000000000000;
    vectors[6]=64'h7fffffffffffffff; vectors[7]=64'h55555555aaaaaaaa;
    for (op=0; op<2; op=op+1)
      for (i=0; i<8; i=i+1)
        for (j=0; j<8; j=j+1) begin
          fn=op ? 10 : 0; a=vectors[i]; b=vectors[j];
          expected=op ? a-b : a+b;
          #1;
          if (y !== expected || adder !== expected) $fatal(1, "MISMATCH");
        end
    $display("PASS"); $finish;
  end
endmodule
