"""Bounded native Spike execution with a Python PLIC, not a DUT result."""
from copy import deepcopy
import ctypes
from pathlib import Path
import time
from .events import MailboxDriver
from rvw.cosim.devices import Plic,PlicMap
from rvw.cosim.platform import Platform
from rvw.cosim.spike import Spike


def run(directory,scenario,config,timeout,shim_inputs):
    plan=scenario['reference_model'];layout=PlicMap(**plan['layout']);model=Plic(layout)
    mmio=[(layout.priority,4*(layout.sources+1)),(layout.pending,4*(layout.sources//32+1)),
          (layout.enable,layout.enable_stride*layout.contexts),(layout.context,layout.context_stride*layout.contexts)]
    platform=Platform(name='project-plic-reference',xlen=64,isa=config.get('isa','rv64im_zicsr_zifencei'),reset_pc=0x80000000,
                      ram=[(0x80000000,128<<20)],mmio=mmio,privilege_modes='MSU')
    cpu=Spike(platform,Path(directory)/scenario['elf'],shim=shim_inputs)
    driver=MailboxDriver(scenario['events']);symbols=cpu.elf.symbols;pending_ack=[]
    context=plan['context'];cause=11 if '-m-' in scenario['id'] else 9
    status='inconclusive';reason='reference instruction or time bound reached';count=0;traps=[]
    def read(address):
        value=ctypes.c_uint64()
        if cpu.lib.rvw_read_physical(cpu.handle,address,ctypes.byref(value)):raise ValueError(cpu.error())
        return value.value
    def write(address,value):
        raw=value.to_bytes(8,'little')
        if cpu.lib.rvw_write(cpu.handle,address,raw,8):raise ValueError(cpu.error())
    def drive(event):
        if event['kind']!='plic-level':raise ValueError('unsupported PLIC stimulus')
        model.set_level(event['source'],event['level'])
    def ack(step):
        event=scenario['events'][len(driver.done)]
        pending_ack.append((count+event.get('settle_ticks',4),step))
    deadline=time.monotonic()+timeout;pc=cpu.elf.entry
    try:
        while count<30000 and time.monotonic()<deadline:
            for tick,step in list(pending_ack):
                if tick<=count:
                    write(symbols['stimulus_ack'],step);pending_ack.remove((tick,step))
            insn=read(pc)&0xffffffff;injected=None;address=None
            if insn&0x7f==3:
                immediate=(insn>>20);immediate-=4096 if immediate&2048 else 0
                address=(cpu.regs[(insn>>15)&31]+immediate)&((1<<64)-1)
                size=1<<((insn>>12)&3)
                if any(base<=address and address+size<=base+length for base,length in mmio):
                    # A pending IRQ may preempt this load. Preview claim side effects.
                    injected=(address,deepcopy(model).read(address,size))
            interrupt=((1<<63)|cause) if model.irq(context) else 0
            effect=cpu.step(interrupt=interrupt,mmio=injected)
            count+=1;pc=effect['pc_next']
            if effect['trap']:traps.append(dict(cause=effect['cause'],interrupt=bool(effect['intr']),pc=hex(effect['pc'])))
            if effect['mem_rmask'] and not effect['mem_fault'] and injected:
                size=effect['mem_rmask'].bit_count()
                actual=model.read(effect['mem_addr'],size)
                if actual!=injected[1]:raise ValueError('PLIC read changed between preview and execution')
            if effect['mem_wmask'] and not effect['mem_fault']:
                address=effect['mem_addr'];size=effect['mem_wmask'].bit_count()
                if any(base<=address and address+size<=base+length for base,length in mmio):
                    model.write(address,effect['mem_wdata']&((1<<(8*size))-1),size)
            request=read(symbols['stimulus_step'])
            driver.service(request,drive,ack)
            tohost=read(symbols['tohost'])
            if tohost:
                status='pass' if tohost==1 and driver.complete and not pending_ack else 'fail'
                reason='Spike program self-check completed' if status=='pass' else 'self-check failed or stimulus incomplete'
                break
    except ValueError as exc:
        reason=str(exc)
    finally:cpu.close()
    return dict(id=scenario['id'],status=status,reason=reason,evidence='model-based',
                scope='native Spike ISA execution with Python PLIC; no DUT coverage',instructions=count,
                traps=traps,stimulus_complete=driver.complete,shim_sha256=shim_inputs['library']['sha256'],
                shim_manifest_sha256=shim_inputs['manifest']['sha256'])
