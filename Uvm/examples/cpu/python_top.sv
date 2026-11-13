module python_top(input bit clk, reset_n, grant, input bit [31:0] instruction,
 output bit request, output bit [31:0] address,
 output bit valid, output longint unsigned order);
 longint unsigned values[19];
 addi_core core(clk,reset_n,grant,instruction,request,address,valid,order,values);
endmodule
