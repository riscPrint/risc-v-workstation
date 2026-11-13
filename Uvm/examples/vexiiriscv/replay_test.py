"""pyuvm CPU environment for complete native VexiiRiscv C2 captures.

This is capture replay, not a live RVFI binding. Vexii exposes a probe.
"""
import hashlib
import json
import os
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
import pyuvm
from cpu_env import LiveCpuEnvironment
from rvw.common.capture import Capture
from rvw.cosim.elf import Elf
from rvw.cosim.platform import Platform
from rvw.cosim.spike import Spike, capture_shim
from rvw.cosim.trace import Trace
from rvw.uvm.cpu_events import CpuEvents
from rvw.uvm.capture_events import CaptureEvents, require_tohost


class CaptureEnvironment(LiveCpuEnvironment):
    async def run_phase(self):
        cfg=self.config
        events=CpuEvents(cfg['reference'],xlen=32)
        stream=CaptureEvents(events,self.scoreboard)
        for row in cfg['records']:
            stream.observe(row)
            await Timer(1,unit='ns')
        stream.finish(cfg['retirements'])
        require_tohost(cfg['records'],cfg['elf'].symbols['tohost'],15)
        Path('cpu-checks-'+cfg['program']+'.json').write_text(json.dumps(dict(
            mode='offline-native-c2-pyuvm',checks=self.scoreboard.checks,traps=events.traps,
            coverage=self.scoreboard.coverage.report()),indent=2)+'\n')
        self.done=True


class CaptureTest(pyuvm.uvm_test):
    def build_phase(self):
        job=self.job
        result=json.loads((Path(job['out'])/'result.json').read_text())
        assert result['status']=='pass', 'native CPU run did not pass'
        elf_path=Path(job['elf'])
        assert result['elf_sha256']==hashlib.sha256(elf_path.read_bytes()).hexdigest(), 'CPU_ELF_IDENTITY'
        trace=Trace(Path(job['out'])/'rvfi.jsonl')
        try:
            records=list(trace)
        finally:
            trace.close()
        count=sum('event' not in r for r in records)
        assert count==result['instret'] and count>0, 'CPU_CAPTURE_COUNT'
        self.capture=Capture(Path('spike-capture-'+elf_path.name))
        shim=capture_shim(self.capture,Path(os.environ['RVW_CPU_SHIM']))
        root=Path(__file__).resolve().parents[3]
        platform=Platform.load(None,root/'examples/vexiiriscv/rvw/platform.json')
        self.reference=Spike(platform,elf_path,shim=shim)
        cfg=dict(elf=Elf(elf_path),memory_base=0x80000000,memory_size=0x1000000,
                 reference=self.reference,records=records,retirements=count,program=elf_path.name)
        pyuvm.ConfigDB().set(self,'env','cpu',cfg)
        self.env=CaptureEnvironment('env',self)
    async def run_phase(self):
        self.raise_objection()
        try:
            for _ in range(100000):
                await Timer(10,unit='ns')
                if self.env.done:return
            raise AssertionError('CPU_CAPTURE_WATCHDOG')
        finally:
            self.reference.close();self.drop_objection()


for index,job in enumerate(json.loads(Path(os.environ['RVW_CPU_CAPTURE_JOBS']).read_text())):
    name='VexiiCapture_'+Path(job['elf']).name.replace('-','_')
    globals()[name]=pyuvm.test()(type(name,(CaptureTest,),{'job':job,'__module__':__name__}))
