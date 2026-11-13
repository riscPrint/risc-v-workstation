"""Measure public run(): file reads, C2 validation/packing, timing and hashes."""
from dataclasses import asdict
import json
from pathlib import Path
import platform
import statistics
import tempfile
from time import perf_counter, process_time
from rvw.ooo import native
from rvw.ooo.core import Config, run


def main():
    native.build(native.library_path())
    count = 500000
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        c=Config(8,64,8,192,8,64,32,32,8,
                 dict(zip(native.KINDS,[1,3,12,1,1,1,1])),branch_penalty=10,branch_speculation=True)
        header=dict(schema='rvw.rvfi/1',xlen=64,core='synthetic',config='synthetic',isa='rv64im',elf='synthetic.elf')
        for name, components in [('integer',{}),('components',{'branch':{'model':'bimodal','entries':1024},
                                      'btb':{'entries':128,'ways':2},
                                      'memory':{'dram_latency':20,'l1d':{'size_kib':32,'ways':8,'latency':2}}})]:
            config=asdict(c);config['components']=components
            cp,tp=root/'config.json',root/'trace.jsonl'
            cp.write_text(json.dumps(config))
            with tp.open('w') as out:
                out.write(json.dumps(header)+'\n')
                for i in range(count):
                    r={k:'0x0' for k in 'pc pc_next insn rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()}
                    r.update({k:0 for k in 'order cycle mode rs1 rs2 rd mem_rmask mem_wmask'.split()})
                    r.update({k:False for k in 'trap intr halt mem_fault'.split()})
                    r.update(order=i,cycle=i,pc=hex(0x100+i%64*4),pc_next=hex(0x104+i%64*4),insn='0x13')
                    if components and i%8==0:
                        r.update(insn='0x2083',rd=1,mem_rmask=15,mem_addr=hex(i%512*4))
                    if components and i%8==7:
                        r.update(insn='0x63',pc_next='0x100')
                    out.write(json.dumps(r)+'\n')
                out.write(json.dumps(dict(event='end',status='pass',cycle=count))+'\n')
            run(cp,tp,10000000)
            seconds=[];cpu_seconds=[]
            for _ in range(4):
                start=perf_counter();cpu=process_time();r=run(cp,tp,10000000);seconds.append(perf_counter()-start);cpu_seconds.append(process_time()-cpu)
            results.append(dict(workload=name,instructions=count,input_bytes=tp.stat().st_size,
                                seconds=seconds, cpu_seconds=cpu_seconds, instructions_per_cpu_second=count/statistics.median(cpu_seconds), instructions_per_second=count/statistics.median(seconds),
                                cycles=r['cycles'],backend=r['backend'],trace_reader=r['trace_reader'],
                                engine_sha256=r['engine_sha256'],trace_sha256=r['trace_sha256'],config_sha256=r['config_sha256']))
    print(json.dumps(dict(host=platform.platform(),machine=platform.machine(),
                         method='one warmup then four public run calls; includes reads, C2 validation, packing, timing, input and engine hashes; generation and native build excluded; synthetic streams',results=results),indent=2))


if __name__=='__main__':
    main()
