#!/usr/bin/env python3
"""Bounded scalar native engine probe on captured project RTL. Writes C1/C2."""
import argparse
import hashlib
import json
import os
import random
from pathlib import Path
import time
from rvw.runs.elf import Elf
from rvw.results import RunResult, save_run
from rvw.sim.native_models import Model


def run(args):
    start=time.monotonic()
    args.out.mkdir(parents=True,exist_ok=False)
    elf=Elf(str(args.elf));memory={}
    for s in elf.segments:
        if s['type']==1:
            for i,b in enumerate(elf.data[s['off']:s['off']+s['filesz']]):memory[s['paddr']+i]=b
    tohost=elf.symbols()['tohost'].value
    ports=json.loads(args.ports.read_text())
    model=Model(args.backend,[args.rtl],'VexTop',ports,args.out/'native',circt=os.environ.get('RVW_CIRCT'),profile=getattr(args,'build_profile',None))
    if model.profile and model.profile.request.get('compiler_pgo')=='generate':
        if model.profile.record['binding']['training_elf_sha256']!=hashlib.sha256(args.elf.read_bytes()).hexdigest():
            raise ValueError('training ELF differs from captured compiler profile request')
    def put(**values):
        for n,v in values.items():model.write(n,v)
        model.eval()
    def read(n):return model.read(n)
    def word(a):return sum(memory.get((a&~3)+i,0)<<(8*i) for i in range(4))
    def mapped(a):return 0x80000000<=a<0x81000000
    rows=[dict(schema='rvw.rvfi/1',xlen=32,core='vexriscv',isa='rv32im_zicsr_zifencei')]
    rng=random.Random(args.seed)
    ip=dp=None
    def inputs():
        put(iBus_cmd_ready=rng.randrange(2),iBus_rsp_valid=int(ip is not None),
            iBus_rsp_payload_inst=ip[0] if ip else 0,iBus_rsp_payload_error=int(ip[1]) if ip else 0,
            dBus_cmd_ready=rng.randrange(2),dBus_rsp_ready=int(dp is not None),
            dBus_rsp_data=dp[0] if dp else 0,dBus_rsp_error=int(dp[1]) if dp else 0)
    execution_start=time.monotonic()
    count=0;status='timeout';cycle=0;handler=False
    try:
        for name,(direction,width) in ports.items():
            if direction=='input':model.write(name,0)
        put(clk=0,reset=1,timerInterrupt=0,externalInterrupt=0,softwareInterrupt=0)
        inputs()
        for _ in range(5):put(clk=1);put(clk=0)
        put(reset=0)
        for cycle in range(1,args.max_cycles+1):
            inputs()
            ni=(word(read('iBus_cmd_payload_pc')),not mapped(read('iBus_cmd_payload_pc'))) if read('iBus_cmd_valid') and read('iBus_cmd_ready') else None
            nd=None
            if read('dBus_cmd_valid') and read('dBus_cmd_ready'):
                a=read('dBus_cmd_payload_address')&~3
                if read('dBus_cmd_payload_wr'):
                    if not mapped(a):raise ValueError('store outside mapped RAM')
                    mask=read('dBus_cmd_payload_mask');value=read('dBus_cmd_payload_data')
                    for i in range(4):
                        if mask>>i&1:memory[a+i]=value>>(8*i)&255
                else:nd=(word(a),not mapped(a))
            if read('trap_valid'):
                if not args.allow_traps:raise ValueError('trap state is outside this bounded probe')
                cause=read('trap_cause')
                rows.append(dict(event='trap',cycle=cycle,cause=hex(cause),tval=hex(read('trap_tval')),interrupt=bool(cause>>31)))
                handler=True
            if read('rvfi_valid'):
                if read('rvfi_order')!=count:raise ValueError('RVFI order discontinuity')
                row=dict(order=count,cycle=cycle,mode=read('rvfi_mode'),trap=bool(read('rvfi_trap')),
                         halt=bool(read('rvfi_halt')),intr=handler or bool(read('rvfi_intr')),mem_fault=False)
                for key,signal in dict(pc='pc_rdata',pc_next='pc_wdata',insn='insn',rs1_rdata='rs1_rdata',
                    rs2_rdata='rs2_rdata',rd_wdata='rd_wdata',mem_addr='mem_addr',mem_rdata='mem_rdata',mem_wdata='mem_wdata').items():
                    row[key]=hex(read('rvfi_'+signal))
                for key,signal in dict(rs1='rs1_addr',rs2='rs2_addr',rd='rd_addr',mem_rmask='mem_rmask',mem_wmask='mem_wmask').items():
                    row[key]=read('rvfi_'+signal)
                rows.append(row);count+=1;handler=False
                if row['mem_wmask'] and int(row['mem_addr'],16)==tohost:
                    status='pass' if int(row['mem_wdata'],16)==1 else 'fail'
                    break
            put(clk=1);put(clk=0);ip,dp=ni,nd
        rows.append(dict(event='end',cycle=cycle,status=status))
        (args.out/'rvfi.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
        result=dict(schema='rvw.run/1',core='vexriscv',config='rv32im',elf=str(args.elf.resolve()),
            elf_sha256=hashlib.sha256(args.elf.read_bytes()).hexdigest(),seed=args.seed,max_cycles=args.max_cycles,
            mem_latency=1,status=status,fail_code=None if status=='pass' else 1,cycles=cycle,instret=count,
            wall_s=time.monotonic()-start,source={},tools={},artifacts={'rvfi_trace':'rvfi.jsonl'},
            details={'execution_s':time.monotonic()-execution_start,'model_compile_s':model.build_seconds,
                     'child_peak_rss_bytes':model.child_peak_rss_bytes,'native_profile':model.profile.record if model.profile else None,
                     'engine':args.backend,'native_identity':model.identity,'initial_state':'zero; then reset',
                     'scope':'bounded seeded-ready, fixed-response-latency probe; no interrupts, wave, CSR snapshot or C4 acceptance'})
        save_run(RunResult.from_dict(result),args.out/'result.json')
        print(json.dumps(result))
        return 0 if status=='pass' else 1
    finally:model.close()


def main():
 p=argparse.ArgumentParser(__doc__)
 p.add_argument('action',nargs='?',choices=['run'],default='run')
 p.add_argument('--backend',choices=['arcilator','verilator'],default=os.environ.get('RVW_NATIVE_ENGINE','arcilator'))
 p.add_argument('--build-profile',type=Path)
 p.add_argument('--ports',type=Path,default=Path(__file__).with_name('engine-ports.json'))
 p.add_argument('--allow-traps',action='store_true')
 p.add_argument('--rtl',type=Path,required=True);p.add_argument('--elf',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True);p.add_argument('--seed',type=int,default=1)
 p.add_argument('--max-cycles',type=int,default=5000);p.add_argument('--rvfi-trace',action='store_true');p.add_argument('--json',action='store_true')
 args=p.parse_args()
 try:return run(args)
 except (OSError,ValueError,KeyError) as error:
  print(json.dumps(dict(status='inconclusive',error=str(error))))
  return 3

if __name__=='__main__':raise SystemExit(main())
