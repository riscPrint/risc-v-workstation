module tb;
reg clk=0; always #5 clk=~clk;
reg reset=1; initial begin repeat(3) @(negedge clk); reset=0; end
wire valid; wire [31:0] pc; reg rsp=0; reg [31:0] insn;
reg [31:0] ram[0:2047]; integer i;
wire dv; wire [31:0] da,dd; wire [3:0] dm;
initial begin for(i=0;i<2048;i=i+1)ram[i]=32'h13; $readmemh("program.hex",ram); #10000; $fatal(1,"timeout"); end
always @(posedge clk) begin
 rsp <= valid && !reset;
 insn <= ram[pc[12:2]];
 if(!reset && dut.rvfi_valid) $display("retire pc=%h insn=%h rd=%d data=%h MEPC=%h",dut.rvfi_pc_rdata,dut.rvfi_insn,dut.rvfi_rd_addr,dut.rvfi_rd_wdata,dut.CsrPlugin_mepc);
 if(!reset && dv) begin
 $display("store addr=%h data=%h",da,dd);
 if(dd==1) $finish;
 end
end
VexRiscv dut(.clk(clk),.reset(reset),.iBus_cmd_valid(valid),.iBus_cmd_ready(1'b1),.iBus_cmd_payload_pc(pc),.iBus_rsp_valid(rsp),.iBus_rsp_payload_inst(insn),.iBus_rsp_payload_error(1'b0),.dBus_cmd_valid(dv),.dBus_cmd_ready(1'b1),.dBus_cmd_payload_address(da),.dBus_cmd_payload_data(dd),.dBus_cmd_payload_mask(dm),.dBus_rsp_ready(1'b0),.dBus_rsp_error(1'b0),.dBus_rsp_data(32'b0),.timerInterrupt(1'b0),.softwareInterrupt(1'b0),.externalInterrupt(1'b0));
endmodule
