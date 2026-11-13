from pathlib import Path
from rvw.formal.architectural_state import monitor
from rvw.formal.riscv import FIELDS
import argparse
p=argparse.ArgumentParser()
p.add_argument('--capture', required=True)
a=p.parse_args()
root=Path(a.capture).resolve()
raw=(root/'picorv32-observed.sv').read_text()
text,widths,outputs=monitor(32, halt=True)
(root/'monitor.sv').write_text(text)
instance='\n'.join(f'wire [{outputs[f]-1}:0] state_rvfi_{f};' for f in FIELDS)
instance+='\nrvw_state_monitor state_monitor(.clock(clk),.reset(!resetn),'+','.join(f'.{k}(state_{k})' for k in widths)+','+','.join(f'.rvfi_{f}(state_rvfi_{f})' for f in FIELDS)+');\n'
instance+='''
`ifdef FORMAL
always @* assume(resetn != $initstate);
`endif
always @(posedge clk) if(resetn) begin
`ifdef FORMAL
    assert(rvfi_valid == state_rvfi_valid);
`else
    if(rvfi_valid !== state_rvfi_valid) $fatal(1, "RVFI mismatch: valid");
`endif
'''
for f in FIELDS:
    if f=='valid': continue
    instance+=f'''`ifdef FORMAL
    if(rvfi_valid) assert(rvfi_{f} == state_rvfi_{f});
`else
    if(rvfi_valid && rvfi_{f} !== state_rvfi_{f}) $fatal(1, "RVFI mismatch: {f}");
`endif
'''
instance+='''
`ifdef FORMAL
    cover(rvfi_valid && rvfi_order > 2);
`endif
end
'''
(root/'miter.sv').write_text(raw.replace('endmodule',instance+'\nendmodule',1))
(root/'miter.sby').write_text('[tasks]\ncheck\ncover\n[options]\ncheck: mode bmc\ncover: mode cover\ndepth 35\n[engines]\nsmtbmc bitwuzla\n[script]\nread -formal -sv miter.sv monitor.sv\nprep -top picorv32\n[files]\nmiter.sv\nmonitor.sv\n')
(root/'tb.sv').write_text('''
module tb;
reg clk=0; always #5 clk=~clk;
reg resetn=0; initial begin repeat(3) @(negedge clk); resetn=1; end
wire mem_valid,mem_instr;wire [31:0] mem_addr,mem_wdata;wire [3:0] mem_wstrb;
reg [31:0] mem_rdata;
reg [31:0] ram[0:255];integer i;integer count=0;
integer program_id;
initial begin
if(!$value$plusargs("program=%d",program_id)) program_id=0;
for(i=0;i<256;i=i+1) ram[i]=32'h00000013;
ram[0]=32'h00500093; // addi x1,x0,5
ram[1]=32'h00308113; // addi x2,x1,3
ram[2]=32'h002081b3; // add x3,x1,x2
ram[3]=32'h10302023; // sw x3,256(x0)
ram[4]=32'h10002203; // lw x4,256(x0)
ram[5]=32'h00418463; // beq x3,x4,+8
ram[6]=32'hfff00293; // skipped
ram[7]=32'h00100293; // addi x5,x0,1
ram[8]=32'hfe1ff06f; // jal x0,-32
if(program_id==1) begin
ram[0]=32'h800000b7; // lui x1,0x80000
ram[1]=32'hfff08113; // addi x2,x1,-1
ram[2]=32'h0020c1b3; // xor x3,x1,x2
ram[3]=32'h40315213; // srai x4,x2,3
ram[4]=32'hff1ff06f; // loop
end
if(program_id==2) begin
ram[0]=32'h00700093; // addi x1,x0,7
ram[1]=32'h00100293; // addi x5,x0,1
ram[2]=32'hfff08093; // addi x1,x1,-1
ram[3]=32'hfe009ee3; // bne x1,x0,-4
ram[4]=32'hff1ff06f; // loop
end
if(program_id==3) begin
ram[0]=32'hfeeff76f; // misaligned JAL from the bounded counterexample; must fail
end
end
always @* mem_rdata=ram[mem_addr[9:2]];
always @(posedge clk) if(mem_valid && |mem_wstrb)
for(i=0;i<4;i=i+1) if(mem_wstrb[i]) ram[mem_addr[9:2]][i*8+:8] <= mem_wdata[i*8+:8];
picorv32 dut(.clk(clk),.resetn(resetn),.mem_valid(mem_valid),.mem_instr(mem_instr),.mem_ready(1'b1),.mem_addr(mem_addr),.mem_wdata(mem_wdata),.mem_wstrb(mem_wstrb),.mem_rdata(mem_rdata),.pcpi_wr(1'b0),.pcpi_rd(32'b0),.pcpi_wait(1'b0),.pcpi_ready(1'b0),.irq(32'b0));
always @(posedge clk) if(resetn && dut.rvfi_valid) begin
count=count+1;
$display("retired %d pc %h rd %d data %h",count,dut.rvfi_pc_rdata,dut.rvfi_rd_addr,dut.rvfi_rd_wdata);
if(count==30) $finish;
end
initial begin #20000; $fatal(1,"retirement timeout"); end
endmodule
''')
