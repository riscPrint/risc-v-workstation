"""Tiny native timing leak fixture. Not a RISC-V core adapter."""
import json
from pathlib import Path
import sys
from rvw.sec.common import native
request, out = Path(sys.argv[1]), Path(sys.argv[2])
r = json.loads(request.read_text())
secret = int(r['secret'])
leak = r['public']['leak']
# Count cycles in RTL. The fixed variant has operand-independent completion.
(out/'toy.sv').write_text('''module tb;
reg clk=0; integer count=0;
always #1 clk=~clk;
always @(posedge clk) begin
 count<=count+1;
 if(count==LIMIT) begin $display("CYCLES %0d",count+1); $finish; end
end
endmodule
'''.replace('LIMIT',str(2+(secret if leak else 0))))
if r['public'].get('isolation'):
    (out/'toy.sv').write_text("""module tb;
reg clk=0; reg privileged=1; integer private_state=SECRET; integer count=0;
always #1 clk=~clk;
initial begin #2; privileged=0; if(FLUSH) private_state=0; end
always @(posedge clk) if(!privileged) begin
 count<=count+1;
 if(count==2+private_state) begin $display("CYCLES %0d",count+1); $finish; end
end
endmodule
""".replace('SECRET',str(secret)).replace('FLUSH',str(int(not leak))))
native(['verilator','--binary','--timing','-Wno-fatal','--top-module','tb','toy.sv'],out)
log=native([str(out/'obj_dir/Vtb')],out)
cycles=int(next(line.split()[1] for line in log.splitlines() if line.startswith('CYCLES ')))
header=dict(schema='rvw.rvfi/1',xlen=32,isa='rv32i',core='tiny-fixture',config='default',elf='synthetic')
records=[header]
for i,_ in enumerate(r['program']):
    row={k:'0x0' for k in 'rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()}
    row.update(order=i,cycle=i,pc=hex(0x100+4*i),pc_next=hex(0x104+4*i),insn='0x13',mode=3,
               rs1=0,rs2=0,rd=0,mem_rmask=0,mem_wmask=0,trap=False,intr=False,halt=False,mem_fault=False)
    records.append(row)
records.append(dict(event='end',cycle=len(records),status='pass'))
# This fixture's architectural model is a fixed NOP stream, independent of timing RTL.
for name in ('reference','rtl'):
    (out/(name+'.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in records))
(out/'response.json').write_text(json.dumps(dict(complete=True,reset_complete=True,
    reference_c2='reference.jsonl',rtl_c2='rtl.jsonl',observations={'cycles':cycles})))
