"""Warmed alternating whole-run decode trials, including cold instruction templates."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import statistics
import tempfile
from time import perf_counter,process_time
from rvw.ooo.core import Config,run


def benchmark(control,candidate,count=500000):
    rows=[]
    with tempfile.TemporaryDirectory(prefix='rvw-decode-speed-') as tmp:
        root=Path(tmp)
        c=Config(8,64,8,192,8,64,32,32,8,dict(alu=1,multiply=3,divide=12,load=1,store=1,branch=1,jump=1),
                 branch_penalty=10,branch_speculation=True)
        for name,diverse,components in [
            ('cached-integer',False,{}),
            ('diverse-integer',True,{}),
            ('diverse-components',True,{'branch':{'model':'bimodal','entries':1024},
                'btb':{'entries':128,'ways':2},'memory':{'dram_latency':20,'l1d':{'size_kib':32,'ways':8,'latency':2}}})]:
            cp,tp=root/'config.json',root/'trace.jsonl'
            data=asdict(c);data['components']=components;cp.write_text(json.dumps(data))
            with tp.open('w') as output:
                output.write(json.dumps(dict(schema='rvw.rvfi/1',xlen=64,core='synthetic',config='synthetic',
                                             isa='rv64imc',elf='synthetic.elf'))+'\n')
                for i in range(count):
                    word=0x13;rd=rs1=rs2=maskr=maskw=address=0
                    pc=0x100+i%64*4;next_pc=pc+4
                    if diverse:
                        imm=i&4095;rs1=i>>12&31;rd=i>>17&31
                        word=0x13|rd<<7|rs1<<15|imm<<20
                        if components and i%8==0:
                            word=0x2003|rd<<7|rs1<<15|imm<<20;maskr=15;address=0x1000+i%2048*4
                        elif components and i%8==3:
                            rs2=i>>20&31;rd=0
                            word=0x2023|rs1<<15|rs2<<20|(imm&31)<<7|(imm>>5)<<25
                            maskw=15;address=0x1000+i%2048*4
                        elif components and i%8==7:
                            rs2=i>>20&31;rd=0;imm=0x1ffc
                            word=0x63|rs1<<15|rs2<<20|(imm>>12&1)<<31|(imm>>11&1)<<7|(imm>>5&63)<<25|(imm>>1&15)<<8
                            next_pc=pc-4
                    row=dict(pc=hex(pc),pc_next=hex(next_pc),insn=hex(word),rs1_rdata='0x0',rs2_rdata='0x0',
                             rd_wdata='0x0',mem_addr=hex(address),mem_rdata='0x0',mem_wdata='0x0',
                             order=i,cycle=i,mode=3,rs1=rs1,rs2=rs2,rd=rd,mem_rmask=maskr,mem_wmask=maskw,
                             trap=False,intr=False,halt=False,mem_fault=False)
                    output.write(json.dumps(row,separators=(',',':'))+'\n')
                output.write(json.dumps(dict(event='end',status='pass',cycle=count))+'\n')
            variants={'control':str(Path(control).resolve()),'candidate':str(Path(candidate).resolve())}
            for library in variants.values():
                os.environ['RVW_OOO_NATIVE']=library;run(cp,tp,10000000)
            results={key:[] for key in variants};reference=None
            for trial in range(4):
                order=list(variants) if trial%2==0 else list(reversed(variants))
                for key in order:
                    os.environ['RVW_OOO_NATIVE']=variants[key]
                    wall,cpu=perf_counter(),process_time();r=run(cp,tp,10000000)
                    elapsed,spent=perf_counter()-wall,process_time()-cpu
                    same={field:r[field] for field in ('cycles','instret','ipc','events','max_occupancy','topdown')}
                    if reference is None:reference=same
                    if same!=reference:raise ValueError('timing or event parity changed during benchmark')
                    results[key].append(dict(wall_s=elapsed,cpu_s=spent,c2_decoder=r['c2_decoder'],
                                             engine_sha256=r['engine_sha256']))
            medians={key:dict(instructions_per_second=count/statistics.median(r['wall_s'] for r in trials),
                              instructions_per_cpu_second=count/statistics.median(r['cpu_s'] for r in trials))
                     for key,trials in results.items()}
            rows.append(dict(workload=name,instructions=count,input_bytes=tp.stat().st_size,
                             trace_sha256=sha256(tp.read_bytes()).hexdigest(),config_sha256=sha256(cp.read_bytes()).hexdigest(),
                             cycles=reference['cycles'],trials=results,medians=medians,
                             wall_speedup=medians['candidate']['instructions_per_second']/medians['control']['instructions_per_second']))
    return dict(host=platform.platform(),machine=platform.machine(),results=rows,
        method='one warmup per variant; four alternating paired public run trials; file reads, validation, packing, scheduling and hashes included',
        limits=['synthetic streams; register values are not an architectural oracle',
                'generation and native compilation excluded; no RTL speed qualification',
                'wall time can reflect other workstation jobs; CPU rates are also retained'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('control');p.add_argument('candidate');p.add_argument('--count',type=int,default=500000)
    args=p.parse_args();print(json.dumps(benchmark(args.control,args.candidate,args.count),indent=2))
