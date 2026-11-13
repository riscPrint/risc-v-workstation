module MemoryMaster(input clk,reset,input rsp_valid,input [31:0] rsp_data,
                    output req_valid,req_write,output [31:0] req_address,req_data,
                    output reg done,error);
  reg [1:0] state;
  assign req_valid = state < 2;
  assign req_write = state == 0;
  assign req_address = 0;
  assign req_data = 32'h12345678;
  always @(posedge clk) begin
    if(reset) begin state<=0;done<=0;error<=0;end
    else if(rsp_valid && state==0) state<=1;
    else if(rsp_valid && state==1) begin
      error<=rsp_data!=32'h12345678;done<=1;state<=2;
    end
  end
endmodule
