#!/usr/bin/env python3
"""Whole captured VexTop through Icarus with an X reset interval."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from rvw.common.proc import run_group
from rvw.runs.elf import Elf


TB=r'''
module tb;
DECLS
VexTop dut(CONNECT);
reg [31:0] ram [0:16383];
integer i,cycle=0,retired=0,active_x=0,inactive_x=0,reset_x=0;
always #5 clk=~clk;
initial begin
  clk=0;reset=1'bx;timerInterrupt=0;externalInterrupt=0;softwareInterrupt=0;
  iBus_cmd_ready=1;dBus_cmd_ready=1;
  iBus_rsp_valid=0;iBus_rsp_payload_inst=0;iBus_rsp_payload_error=0;
  dBus_rsp_ready=0;dBus_rsp_data=0;dBus_rsp_error=0;
  $readmemh("memory.hex",ram);
  repeat(2) @(negedge clk); #1;
  reset=1;
  repeat(5) @(negedge clk); #1;
  reset=0;
end
always @(posedge clk) begin
  if(reset !== 1'b0) begin iBus_rsp_valid<=0;dBus_rsp_ready<=0;end
  else begin
    iBus_rsp_valid<=iBus_cmd_valid;
    iBus_rsp_payload_inst<=ram[(iBus_cmd_payload_pc-32'h80000000)>>2];
    iBus_rsp_payload_error<=iBus_cmd_payload_pc<32'h80000000 || iBus_cmd_payload_pc>=32'h80010000;
    dBus_rsp_ready<=dBus_cmd_valid && !dBus_cmd_payload_wr;
    dBus_rsp_data<=ram[(dBus_cmd_payload_address-32'h80000000)>>2];
    dBus_rsp_error<=dBus_cmd_payload_address<32'h80000000 || dBus_cmd_payload_address>=32'h80010000;
    if(dBus_cmd_valid && dBus_cmd_payload_wr) begin
      if(dBus_cmd_payload_address<32'h80000000 || dBus_cmd_payload_address>=32'h80010000)
        $fatal(1,"store outside RAM");
      for(i=0;i<4;i=i+1) if(dBus_cmd_payload_mask[i])
        ram[(dBus_cmd_payload_address-32'h80000000)>>2][8*i +: 8]<=dBus_cmd_payload_data[8*i +: 8];
    end
  end
end
always @(negedge clk) begin
  if(reset === 1'bx) begin
    if((^{rvfi_valid,rvfi_pc_rdata}) === 1'bx) reset_x=reset_x+1;
  end
  if(reset === 1'b0) begin
    cycle=cycle+1;
    if(rvfi_valid === 1'bx) active_x=active_x+1;
    if(rvfi_valid === 1'b1) begin
      if(rvfi_order !== retired) $fatal(1,"RVFI order");
      if((^{rvfi_insn,rvfi_pc_rdata,rvfi_pc_wdata,rvfi_rd_addr,rvfi_rs1_addr,rvfi_rs2_addr,
            rvfi_mem_rmask,rvfi_mem_wmask,rvfi_trap,rvfi_mode}) === 1'bx) active_x=active_x+1;
      if(rvfi_rd_addr!=0 && (^rvfi_rd_wdata) === 1'bx) active_x=active_x+1;
      if(rvfi_rs1_addr!=0 && (^rvfi_rs1_rdata) === 1'bx) active_x=active_x+1;
      if(rvfi_rs2_addr!=0 && (^rvfi_rs2_rdata) === 1'bx) active_x=active_x+1;
      if(rvfi_mem_wmask!=0 && (^{rvfi_mem_addr,rvfi_mem_wdata}) === 1'bx) active_x=active_x+1;
      if(rvfi_mem_rmask!=0 && (^{rvfi_mem_addr,rvfi_mem_rdata}) === 1'bx) active_x=active_x+1;
      if(rvfi_mem_wmask==0 && (^rvfi_mem_wdata) === 1'bx) inactive_x=inactive_x+1;
      if(rvfi_mem_rmask==0 && (^rvfi_mem_rdata) === 1'bx) inactive_x=inactive_x+1;
      retired=retired+1;
      if(rvfi_mem_wmask!=0 && rvfi_mem_addr==TOHOST) begin
        $display("RVW_X_REPORT cycles=%0d retired=%0d reset_x=%0d active_x=%0d inactive_x=%0d",cycle,retired,reset_x,active_x,inactive_x);
        if(rvfi_mem_wdata !== 1 || active_x!=0) $fatal(1,"unknown or failed terminal store");
        $display("RVW_FOUR_STATE_PASS");$finish;
      end
    end
    if(cycle>=5000) $fatal(1,"cycle bound");
  end
end
endmodule
'''


def run(rtl,elf,out):
    rtl=Path(rtl).resolve(strict=True);elf=Path(elf).resolve(strict=True);out=Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    loaded=Elf(str(elf));memory=bytearray(65536)
    for s in loaded.segments:
        if s['type']==1:
            offset=s['paddr']-0x80000000
            if offset<0 or offset+s['filesz']>len(memory):raise ValueError('ELF outside probe RAM')
            memory[offset:offset+s['filesz']]=loaded.data[s['off']:s['off']+s['filesz']]
    (out/'memory.hex').write_text(''.join(f'{int.from_bytes(memory[i:i+4],"little"):08x}\n' for i in range(0,len(memory),4)))
    ports=json.loads(Path(__file__).with_name('engine-ports.json').read_text())
    decls='\n'.join(f'{"reg" if d=="input" else "wire"} '+(f'[{w-1}:0] ' if w>1 else '')+n+';' for n,(d,w) in ports.items())
    tb=TB.replace('DECLS',decls).replace('CONNECT',','.join(f'.{n}({n})' for n in ports))
    tb=tb.replace('TOHOST',"32'h"+f'{loaded.symbols()["tohost"].value:x}')
    (out/'tb.sv').write_text(tb)
    def step(argv,name):
        result=run_group(['nice','-n','10',*map(str,argv)],cwd=out,timeout=60,capture=True)
        (out/(name+'.log')).write_text(result.stdout+result.stderr)
        return result
    iv,vvp=shutil.which('iverilog'),shutil.which('vvp')
    if not iv or not vvp:raise ValueError('native Icarus and vvp required')
    version=step([iv,'-V'],'version').stdout.splitlines()[0]
    built=step([iv,'-g2012','-s','tb','-o',out/'sim',rtl,out/'tb.sv'],'build')
    if built.returncode or built.timed_out:raise ValueError('Icarus build failed; see build.log')
    result=step([vvp,out/'sim'],'run')
    match=re.search(r'RVW_X_REPORT cycles=(\d+) retired=(\d+) reset_x=(\d+) active_x=(\d+) inactive_x=(\d+)',result.stdout)
    counts=dict(zip(('cycles','retired','reset_x','active_x','inactive_x'),map(int,match.groups()))) if match else {}
    report=dict(status='pass' if result.returncode==0 and not result.timed_out and match and
                'RVW_FOUR_STATE_PASS' in result.stdout else 'inconclusive',counts=counts,
                returncode=result.returncode,timed_out=result.timed_out,tool_version=version,
                inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (rtl,elf,out/'tb.sv')},
                scope='whole captured core; X reset followed by known reset; active-field checks only',
                x_semantics='Icarus four-state events; procedural if is not pessimistic xprop')
    (out/'four-state.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('rtl','elf','out'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    report=run(args.rtl,args.elf,args.out);print(json.dumps(report))
    raise SystemExit(0 if report['status']=='pass' else 3)
