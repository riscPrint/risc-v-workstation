"""A live scalar CPU bench from the adapter's declared memory and RVFI roles."""
import json
from pathlib import Path
from rvw.sim.uvm import require_evidence


def discover(db):
    from rvw.query.db import DesignDB
    for parent in Path(db).resolve().parents:
        path=parent/'rvw/core-map.json'
        if path.is_file():
            core=json.loads(path.read_text())
            if core['xlen'] != 32 or not core['rvfi'] or any(b['protocol']!='req-rsp' or 'rsp_ready' in b['signals'] for b in core['buses']):
                return None
            design=DesignDB(db)
            try:
                tops=design.q('SELECT module FROM components WHERE parent_id IS NULL')
                expected=core['top'].get('module',core['top'].get('class','').split('.')[-1])
                if tops != [(expected,)]:
                    raise ValueError('mapped core top differs from the design database')
            finally: design.close()
            return parent,core
    return None


def generate(db, out, *, uvm=False):
    found=discover(db)
    if found is None:
        raise ValueError('no supported project core-map beside the selected database')
    root,core=found
    target=Path(out).resolve()
    if uvm:
        target.mkdir(parents=True,exist_ok=False)
        test=target/'test_mapped.py'
        manifest=target/'bench.json'
    else:
        test=target;test.parent.mkdir(parents=True,exist_ok=True)
        manifest=test.with_suffix('.bench.json')
    config=dict(root=str(root),core=core)
    text='''import cocotb
from rvw.vip.mapped import run
CONFIG = CONFIG_VALUE
@cocotb.test()
async def mapped_cpu(dut):
    await run(dut, CONFIG)
'''.replace('CONFIG_VALUE',repr(config))
    if uvm:
        text='''import cocotb
import pyuvm
from rvw.vip.mapped import run
CONFIG = CONFIG_VALUE
@pyuvm.test()
class MappedCpuTest(pyuvm.uvm_test):
    async def run_phase(self):
        self.raise_objection()
        try:
            await run(cocotb.top, CONFIG)
        finally:
            self.drop_objection()
'''.replace('CONFIG_VALUE',repr(config))
    with test.open('x') as f:f.write(text)
    spec=dict(schema='rvw.cocotb/1',name='mapped_cpu',backend='verilator',
              top=core['top'].get('module',core['top'].get('class','').split('.')[-1]),
              sources=[str(root/'rvw/out/export/core.v')],test_module=test.stem,
              python_paths=[str(test.parent)],requires=['timer'])
    with manifest.open('x') as f:json.dump(spec,f,indent=2)
    return dict(status='generated',manifest=str(manifest),path=str(test),profile='mapped_cpu',
                next=['Run rvw/export-rtl.sh, then rvw regress cocotb with the generated manifest.'],
                limits=['Native execution is required. The bench checks the project smoke ELF with Spike.'])


async def run(dut, config):
    """One outstanding response per declared bus; live Spike retirement checks."""
    import os
    from cocotb.triggers import Timer
    from rvw.cosim.elf import Elf
    from rvw.sim.cpu_env import CpuMemory,CpuScoreboard,spike_reference
    core=config['core'];root=Path(config['root'])
    elf_path=Path(os.environ.get('RVW_ELF',root/'rvw/out/programs/smoke'))
    elf=Elf(elf_path)
    memory=CpuMemory(int(core['ram']['base'],0),int(core['ram']['size'],0),max_wait=0)
    memory.preload(elf)
    if 'tohost' not in elf.symbols:
        raise ValueError('mapped bench ELF needs tohost')
    reference=spike_reference(root/'rvw/cosim.json',elf_path,Path(os.environ.get('RVW_BENCH_WORK','reference')))
    scoreboard=CpuScoreboard(reference)
    top=core['top'];clock=top.get('clock','clk');reset=top.get('reset','reset')
    active=0 if top.get('reset_active')=='low' else 1
    def put(n,v):getattr(dut,n).value=v
    def get(n):return int(getattr(dut,n).value)
    for pin,value in core['constants'].items():put(pin,int(value,0))
    for pin in core.get('irq',{}).values():put(pin,0)
    output=[]
    pending={}
    buses=[] if config.get('internal_memory') else core['buses']
    prefix=core['rvfi']['prefix']
    names=dict(pc='pc_rdata',pc_next='pc_wdata',rs1='rs1_addr',rs2='rs2_addr',rd='rd_addr')
    from rvw.sim.cpu_env import CpuScoreboard as SB
    fields=set(SB.fields+['order','rs1','rs1_rdata','rs2','rs2_rdata','intr','halt'])
    try:
        for cycle in range(20000):
            put(clock,0);put(reset,active if cycle<8 else 1-active)
            requests=[]
            for i,b in enumerate(buses):
                s=b['signals']
                if 'cmd_ready' in s:put(s['cmd_ready'],1)
                reply=pending.pop(i,None)
                put(s['rsp_valid'],int(reply is not None));put(s['rdata'],reply.data if reply else 0)
                if 'error' in s:put(s['error'],int(reply.error) if reply else 0)
            await Timer(5,unit='ns')
            if cycle>=8:
                for i,b in enumerate(buses):
                    s=b['signals']
                    if get(s['cmd_valid']):
                        write=bool(get(s['write'])) if 'write' in s else False
                        reply=memory.access(get(s['address']) & ~3,write=write,
                                            data=get(s['wdata']) if 'wdata' in s else 0,
                                            mask=get(s['mask']) if 'mask' in s else 15)
                        if not write or b['write_response']:pending[i]=reply
            put(clock,1)
            await Timer(5,unit='ns')
            if cycle>=8 and get(prefix+'valid'):
                record={n:get(prefix+names.get(n,n)) for n in fields if n!='mem_fault'}
                record['mem_fault']=0
                scoreboard.observe(record)
                if config.get('output_symbol') and record['mem_wmask'] and record['mem_addr']==elf.symbols[config['output_symbol']]:
                    output.append(record['mem_wdata'] & 255)
                if record['mem_wmask'] and record['mem_addr']==elf.symbols['tohost']:
                    require_evidence(record['mem_wdata']==1, 'tohost failure')
                    scoreboard.finish(scoreboard.checks)
                    if 'expected_output' in config:
                        require_evidence(bytes(output).decode()==config['expected_output'], 'output mismatch')
                        dut._log.info('CPU output: %s', bytes(output).decode())
                    dut._log.info('Spike checked %d live retirements',scoreboard.checks)
                    return
        raise AssertionError('mapped CPU watchdog expired')
    finally:
        reference.close()
