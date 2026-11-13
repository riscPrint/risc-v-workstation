"""Tiny Verilator key-register fault fixture. Architectural trace is one NOP."""
import argparse
import json
from pathlib import Path
from rvw.sec.common import native
p=argparse.ArgumentParser();p.add_argument('command');p.add_argument('--elf');p.add_argument('--out');p.add_argument('--rvfi-trace',action='store_true');p.add_argument('--fault')
a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
f=json.loads(Path(a.fault).read_text())['faults'][0] if a.fault else None
protected=Path(a.elf).read_text().strip()=='protected'
mask=(1<<f['bit']) if f else 0
(out/'toy.sv').write_text('''module tb;
reg clk=0;reg reset=1;reg inject=0;reg [7:0] key;reg parity;
wire alarm=PROTECTED && ((^key)!=parity);
always @(posedge clk) begin
 if(reset) begin key<=8'd1;parity<=1;end
 else if(inject) key<=key ^ MASK;
end
initial begin
#1;clk=1;#1;clk=0;reset=0;inject=1;#1;clk=1;#1;
$display("OBS %0d %0d",key,alarm);$finish;
end
endmodule
'''.replace('PROTECTED',str(int(protected))).replace('MASK',f"8'd{mask}"))
native(['verilator','--binary','--timing','-Wno-fatal','--top-module','tb','toy.sv'],out)
log=native([str(out/'obj_dir/Vtb')],out)
key,alarm=map(int,next(line for line in log.splitlines() if line.startswith('OBS ')).split()[1:])
header=dict(schema='rvw.rvfi/1',xlen=32,isa='rv32i',core='tiny-fixture',config='default',elf=a.elf)
r={k:'0x0' for k in 'rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()}
r.update(order=0,cycle=0,pc='0x100',pc_next='0x104',insn='0x13',mode=3,rs1=0,rs2=0,rd=0,mem_rmask=0,mem_wmask=0,trap=False,intr=False,halt=False,mem_fault=False)
(out/'trace.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in [header,r,dict(event='end',cycle=1,status='pass')]))
(out/'security-observations.json').write_text(json.dumps({'debug_bus':key}))
details={'detections':['key_parity'] if alarm else []}
if f: details['fault']={'applied':True,'site':f['site'],'cycle':f['cycle'],'bit':f['bit']}
(out/'result.json').write_text(json.dumps(dict(schema='rvw.run/1',status='pass',details=details,artifacts={'rvfi_trace':'trace.jsonl'})))
