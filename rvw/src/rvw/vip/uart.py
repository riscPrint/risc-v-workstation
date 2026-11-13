"""UART serial agents with integer clock-to-baud ratio and optional cocotb."""
from collections import Counter, deque
from dataclasses import dataclass, replace
import random
from .apb import ProtocolError


@dataclass(frozen=True)
class Config:
    cycles_per_bit: int = 8
    data_bits: int = 8
    parity: str = 'none'
    stop_bits: int = 1
    def __post_init__(self):
        if self.cycles_per_bit<4 or self.data_bits not in range(5,10) or self.parity not in ('none','even','odd') or self.stop_bits not in (1,2):
            raise ValueError('unsupported UART framing or timing')


@dataclass(frozen=True)
class Frame:
    data: int
    parity_error: bool = False
    framing_error: bool = False


def encode(frame,config=Config()):
    if not 0<=frame.data<(1<<config.data_bits): raise ValueError('UART data width')
    bits=[0]+[(frame.data>>i)&1 for i in range(config.data_bits)]
    if config.parity!='none':
        bits.append((frame.data.bit_count()%2)^int(config.parity=='odd')^frame.parity_error)
    bits += [int(not frame.framing_error)]*config.stop_bits
    return tuple(bit for bit in bits for _ in range(config.cycles_per_bit))


class Monitor:
    """Sample at bit centres. Invalid frames are observations, not test passes."""
    def __init__(self,hook=lambda frame:None,config=Config()):
        self.config,self.hook=config,hook; self.coverage=Counter(); self.reset()
    def reset(self):
        self.state='idle'; self.remaining=0; self.index=0; self.data=0
        self.parity_error=self.framing_error=False
    def sample(self,line,reset_n=True):
        if not reset_n: self.reset(); self.coverage['reset']+=1; return
        if line not in (0,1): raise ProtocolError('UART_UNKNOWN_LINE')
        c=self.config
        if self.state=='recover':
            if line: self.state='idle'
            return
        if self.state=='idle':
            if not line:
                self.state='start'; self.remaining=c.cycles_per_bit//2
            return
        self.remaining-=1
        if self.remaining: return
        self.remaining=c.cycles_per_bit
        if self.state=='start':
            if line: self.state='idle'; self.coverage['false_start']+=1
            else: self.state='data'; self.index=0; self.data=0
        elif self.state=='data':
            self.data |= line<<self.index; self.index+=1
            if self.index==c.data_bits:
                self.state='stop' if c.parity=='none' else 'parity'; self.index=0
        elif self.state=='parity':
            self.parity_error=line!=((self.data.bit_count()%2)^int(c.parity=='odd'))
            self.state='stop'
        elif self.state=='stop':
            self.framing_error |= not line; self.index+=1
            if self.index==c.stop_bits:
                frame=Frame(self.data,self.parity_error,self.framing_error)
                self.coverage[('data',self.data)]+=1
                self.coverage[('parity_error',frame.parity_error)]+=1
                self.coverage[('framing_error',frame.framing_error)]+=1
                self.hook(frame)
                self.reset()
                if frame.framing_error: self.state='recover'


class Scoreboard:
    def __init__(self): self.expected=deque(); self.count=0
    def expect(self,frame): self.expected.append(frame)
    def observe(self,frame):
        if not self.expected or self.expected.popleft()!=frame: raise ProtocolError('UART_BYTE_STREAM')
        self.count+=1
    def finish(self):
        if self.expected or not self.count: raise ProtocolError('UART_MISSING_FRAME')


class Driver:
    def __init__(self,tick,config=Config()): self.tick,self.config=tick,config
    def send(self,frame):
        for bit in encode(frame,self.config): self.tick(bit)
        # A high idle bit permits recovery after an injected stop error.
        for _ in range(self.config.cycles_per_bit): self.tick(1)


Manager=Driver
Subordinate=Driver  # UART is full duplex. Both roles use the same framing.


class Fifo:
    """Reference receive FIFO with explicit software read and IRQ thresholds."""
    def __init__(self,depth=4,threshold=1):
        if depth<1 or not 1<=threshold<=depth: raise ValueError('UART FIFO limits')
        self.depth,self.threshold=depth,threshold; self.reset()
    def reset(self): self.queue=deque(); self.overrun=False; self.error=False
    def receive(self,frame):
        self.error |= frame.parity_error or frame.framing_error
        if len(self.queue)==self.depth: self.overrun=True
        else: self.queue.append(frame)
    def read(self): return self.queue.popleft() if self.queue else None
    def check_status(self,level,irq,overrun,error):
        if (level,bool(irq),bool(overrun),bool(error)) != (len(self.queue),self.irq,self.overrun,self.error):
            raise ProtocolError('UART_FIFO_STATUS')
    def check_read(self,observed):
        if observed!=self.read(): raise ProtocolError('UART_FIFO_DATA')
    @property
    def irq(self): return len(self.queue)>=self.threshold or self.overrun or self.error


class Loopback:
    """Seeded delayed serial fixture; bug variant changes the first data bit."""
    def __init__(self,seed=1,config=Config(),buggy=False):
        self.rng=random.Random(seed); self.config=config; self.buggy=buggy
        self.queue=deque(); self.monitor=Monitor(self.receive,config)
    def receive(self,frame):
        self.queue.extend([1]*(self.rng.randrange(4)*self.config.cycles_per_bit))
        if self.buggy: frame=replace(frame,data=frame.data^1)
        self.queue.extend(encode(frame,self.config))
        self.queue.extend([1]*self.config.cycles_per_bit)
    def step(self,tx,reset_n=True):
        if not reset_n: self.queue.clear()
        self.monitor.sample(tx,reset_n)
        return self.queue.popleft() if self.queue else 1


def sequences(seed=1,count=32,config=Config()):
    rng=random.Random(seed)
    yield Frame(0); yield Frame((1<<config.data_bits)-1)
    for _ in range(count): yield Frame(rng.randrange(1<<config.data_bits))


def inject(frame,fault='parity'):
    if fault=='parity': return replace(frame,parity_error=True)
    if fault=='stop': return replace(frame,framing_error=True)
    if fault=='data': return replace(frame,data=frame.data^1)
    raise ValueError(fault)


class CocotbAgent:
    """Independent full-duplex UART endpoint. tx/rx are named from DUT view."""
    def __init__(self,dut,tx='tx',rx='rx',config=Config(),hook=lambda frame:None):
        self.dut,self.tx,self.rx,self.config=dut,tx,rx,config
        self.monitor=Monitor(hook,config)
    async def send(self,frame):
        from cocotb.triggers import FallingEdge
        for bit in (*encode(frame,self.config),*[1]*self.config.cycles_per_bit):
            await FallingEdge(self.dut.clk); getattr(self.dut,self.rx).value=bit
    async def run_monitor(self):
        from cocotb.triggers import RisingEdge
        while True:
            await RisingEdge(self.dut.clk)
            self.monitor.sample(int(getattr(self.dut,self.tx).value),int(self.dut.reset_n.value))
    async def run_subordinate(self,seed=1):
        import cocotb
        from cocotb.queue import Queue
        queue=Queue(); self.monitor.hook=queue.put_nowait
        task=cocotb.start_soon(self.run_monitor())
        rng=random.Random(seed)
        from cocotb.triggers import ClockCycles
        try:
            while True:
                frame=await queue.get()
                await ClockCycles(self.dut.clk,rng.randrange(1,4)*self.config.cycles_per_bit)
                await self.send(frame)
        finally: task.cancel()
