#!/usr/bin/env python3
"""Bounded live ADDI/MISA Spike smoke; use an existing matched ABI 8 shim."""
import argparse
import json
import datetime as dt
import re
from pathlib import Path
from rvw.common.capture import Capture
from rvw.common.proc import run_group
from rvw.cosim.elf import Elf
from rvw.cosim.spike import capture_shim, FIELDS, SHIM_VERSION
from rvw.sim import uvm
from rvw.results import write_json


def run(out, shim, archive, *, build_timeout=600):
    if SHIM_VERSION != 8:
        raise ValueError('unsupported:live_cpu_spike_abi')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    c = Capture(out/'capture')
    captured = capture_shim(c, shim)
    source = out/'program.elf'
    result = run_group(['nice','-n','10','/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc',
        '-nostdlib','-march=rv32i_zicsr','-mabi=ilp32','-Wl,-T,'+str(here/'program.ld'),
        '-Wl,--no-relax',str(here/'program.S'),'-o',str(source)],capture=True,timeout=10)
    if result.returncode or result.timed_out:
        raise ValueError('fixture ELF build failed: '+result.stderr)
    elf=Elf(source)
    image=out/'image.txt'
    image.write_text(''.join(f'{address+i:x} {byte:x}\n'
        for address,data,memsz in elf.segments for i,byte in enumerate(data)))
    (out/'spike_effect.h').write_text('#include <cstdint>\nstruct Effect {\n'+''.join(
        f'uint64_t {field};\n' for field in FIELDS)+'uint64_t regs[32]; char disasm[256];\n};\n')
    args=[json.dumps(captured['library']['copy']), json.dumps(captured['source']['sha256']),
          json.dumps(captured['manifest_data']['build_id']), '"rv32i_zicsr"', '"M"',
          '32','0','0','1',"64'h80000000",'4096',"64'h80000000",json.dumps(str(image)),'4']
    (out/'spike_setup.svh').write_text('''
 import "DPI-C" function int rvw_uvm_init(input string lib, source_hash, build_hash,
 input string isa, modes, input int unsigned bits, pmp, input int absent_zero, align,
 input longint unsigned base, size, pc, input string image, input longint unsigned grain);
 initial begin
  if(rvw_uvm_init('''+','.join(args)+''')!=0) $fatal(1,"Spike init: %s",rvw_uvm_error());
  shared_memory=new("memory");
  uvm_config_db#(cpu_memory)::set(null,"uvm_test_top.env","memory",shared_memory);
  uvm_config_db#(virtual rvw_cpu_if)::set(null,"*","vif",bus);
  run_test("cpu_smoke");
 end
''')
    library=uvm.unpack(archive,out/'library')
    command=['nice','-n','10','verilator','--binary','--timing','--assert','-Wno-fatal',
        '-j','2','--top-module','top','+define+UVM_NO_DPI',
        '+incdir+'+str(library/'src'),'+incdir+'+str(out),str(library/'src/uvm_pkg.sv'),
        str(root/'cpu/rvw_cpu_if.sv'),str(root/'cpu/rvw_cpu_pkg.sv'),
        str(here/'fixture.sv'),str(here/'top.sv'),str(root/'spike_bridge.cpp'),
        '-CFLAGS','-I'+str(out),'--Mdir',str(out/'obj'),
        '-MAKEFLAGS','OPT_FAST=-O0 OPT_SLOW=-O0']
    with (out/'build.log').open('w') as log:
        result=run_group(command,timeout=build_timeout,stdout=log,stderr=log)
    if result.returncode or result.timed_out:
        raise ValueError('native build failed; see build.log')
    rows=[]
    for seed,negative in [(1,False),(3,False),(1,True),(1,'state'),(1,'csr')]:
        name=(str(negative)+'-fault') if negative else 'seed-'+str(seed)
        folder=out/name; folder.mkdir()
        cmd=['nice','-n','10',str(out/'obj/Vtop'),'+image='+str(image),f'+verilator+seed+{seed}']
        if negative: cmd.append({'state':'+corrupt_state','csr':'+corrupt_csr'}.get(negative,'+corrupt'))
        with (folder/'run.log').open('w') as log:
            result=run_group(cmd,timeout=10,stdout=log,stderr=log)
        text=(folder/'run.log').read_text()
        errors=re.search(r'^\s*UVM_(?:ERROR|FATAL)\b(?!\s*:\s*0\s*$)',text,re.M)
        good=not result.timed_out and (
            result.returncode!=0 and '[SPIKE_MISMATCH]' in text and 'RVW_UVM_DONE' not in text
            if negative else result.returncode==0 and not errors
            and text.splitlines().count('RVW_UVM_DONE cpu_smoke checks=6')==1)
        status='pass' if good else 'error'
        trace_artifact={}
        if good and not negative:
            columns='pc pc_next insn mode rd rd_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata trap mem_fault rs1 rs1_rdata rs2 rs2_rdata intr halt'.split()
            records=[]
            for line in text.splitlines():
                if not line.startswith('RVW_CPU_RETIRE '): continue
                parts=line.split()
                row=dict(zip(columns,(int(v,16) for v in parts[3:])))
                row.update(order=int(parts[1]),cycle=int(parts[2]))
                for key in ('trap','mem_fault','intr','halt'): row[key]=bool(row[key])
                for key in ('pc','pc_next','insn','rd_wdata','rs1_rdata','rs2_rdata','mem_addr','mem_rdata','mem_wdata'):
                    row[key]=hex(row[key])
                records.append(row)
            if len(records)!=6: raise ValueError('missing live trace records')
            header=dict(schema='rvw.rvfi/1',core='addi_fixture',config='live-scalar',
                        xlen=32,isa='rv32i_zicsr',elf=str(source))
            end=dict(event='end',cycle=records[-1]['cycle']+1,status='pass')
            (folder/'rvfi.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in [header,*records,end]))
            trace_artifact={'rvfi_trace':'rvfi.jsonl'}
        write_json(folder/'result.json',dict(schema='rvw.run/1',core='addi_fixture',
            config='live-scalar',seed=seed,status=status,
            cycles=records[-1]['cycle'] if good and not negative else None,
            instret=6 if good and not negative else None,
            source={'identity_complete':False},details={'negative':negative},
            elf=str(source),elf_sha256=uvm.sha(source),
            artifacts={'log':'run.log',**trace_artifact}))
        rows.append(dict(id=({'state':'spike_state_fault_detection','csr':'spike_csr_fault_detection'}.get(negative,'spike_fault_detection')) if negative else 'spike_retirements',
            seed=seed,kind='uvm',status=status,signature=None if good else 'uvm:live-incomplete',
            **({} if good else {'inconclusive':'missing live CPU conformance evidence'}),
            artifacts={'run':name+'/result.json','log':name+'/run.log'}))
    c.verify_tools()
    report=dict(schema='rvw.results/1',suite='live-addi-fixture',core='addi_fixture',
        config='live-scalar',run_id=out.name,created=dt.datetime.now(dt.timezone.utc).isoformat(),
        source={'identity_complete':False},tests=rows,build_command=command,
        profile='scalar-addi-misa-six-retirements',uvm_commit=uvm.COMMIT)
    write_json(out/'results.json',report)
    if not all(row['status']=='pass' for row in rows):
        raise ValueError('live CPU checks failed; see results.json and logs')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--shim',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--build-timeout',type=float,default=600)
    a=p.parse_args()
    print(json.dumps(run(a.out,a.shim,a.archive,build_timeout=a.build_timeout)))
