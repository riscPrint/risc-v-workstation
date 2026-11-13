"""Run the existing SMP hart programs with an optional RTL peripheral host."""
import json
import os
from collections import deque
from pathlib import Path
import cocotb
from cocotb.triggers import FallingEdge,RisingEdge
from rvw.cosim.elf import Elf
from rvw.sim.bench import start


@cocotb.test()
async def peripheral_host(d):
    directory=Path(os.environ['RVW_SMP_PROGRAMS'])
    memory={};hosts=[]
    for h in range(2):
        image=Elf(directory/f'hart-{h}.elf');hosts.append(image.symbols['tohost'])
        for base,data,size in image.segments:
            for n in range(size):memory[base+n]=data[n] if n<len(data) else 0
    def read(address,size):return sum(memory.get(address+n,0)<<(n*8) for n in range(size))
    def get(name):return int(getattr(d,name).value)
    def put(name,value):getattr(d,name).value=value
    queues={};done=[0,0];requests=[0,0]
    for h in range(2):
        put(f'gpio{h}_input',0)
        for kind in ('fetch','lsu'):
            prefix=f'ports_{kind}_{h}'
            queues[prefix]=deque()
            put(prefix+'_cmd_ready',0);put(prefix+'_rsp_valid',0)
            put(prefix+'_rsp_payload_id',0);put(prefix+'_rsp_payload_error',0)
            put(prefix+'_rsp_payload_'+('word' if kind=='fetch' else 'data'),0)
            if kind=='lsu':put(prefix+'_rsp_payload_scMiss',0)
    await start(d)
    for cycle in range(1,20001):
        await FallingEdge(d.clk)
        for h in range(2):
            for kind in ('fetch','lsu'):
                p=f'ports_{kind}_{h}';q=queues[p]
                put(p+'_cmd_ready',int(len(q)<4))
                response=q.popleft() if q and q[0][0]<=cycle else None
                put(p+'_rsp_valid',int(response is not None))
                if response:
                    _,ident,value,error=response
                    put(p+'_rsp_payload_id',ident);put(p+'_rsp_payload_error',error)
                    put(p+'_rsp_payload_'+('word' if kind=='fetch' else 'data'),value)
        await RisingEdge(d.clk)
        for h in range(2):
            for kind in ('fetch','lsu'):
                p=f'ports_{kind}_{h}'
                if not(get(p+'_cmd_valid') and get(p+'_cmd_ready')):continue
                address=get(p+'_cmd_payload_address');ident=get(p+'_cmd_payload_id')
                n=len(getattr(d,p+'_rsp_payload_'+('word' if kind=='fetch' else 'data')))//8
                base=address & ~(n-1);value=read(base,n)
                error=int(not(0x80000000<=base and base+n<=0x82000000))
                if kind=='lsu':
                    assert not get(p+'_cmd_payload_amoEnable'),'THIS_BENCH_REQUIRES_THE_SMP_ATOMIC_SERVICE_FOR_AMOS'
                    requests[h]+=1
                    if get(p+'_cmd_payload_write') and not error:
                        data=get(p+'_cmd_payload_data');mask=get(p+'_cmd_payload_mask')
                        for lane in range(n):
                            if mask>>lane&1:memory[base+lane]=data>>(lane*8)&255
                        if base==hosts[h]:done[h]=read(base,8)
                queues[p].append((cycle+2+(h+cycle)%3,ident,value,error))
        if any(code not in (0,1) for code in done):break
        if all(done):break
    report=dict(cycles=cycle,tohost=done,retired=[get(f'core_retired_{h}') for h in range(2)],
                mmio=[get(f'core_mmio_{h}') for h in range(2)],ram_data_requests=requests,
                gpio=[get(f'gpio{h}_output') for h in range(2)])
    Path('smp-host-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    assert done==[1,1],'ALL_HARTS_MUST_PASS'
    assert all(report['retired']) and report['mmio']==[2,2],'ALL_HARTS_MUST_USE_RTL_MMIO'
    assert report['gpio']==[0x12340000,0x12340001],'RTL_GPIO_VALUES'
