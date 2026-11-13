"""Single-port SRAM/ROM, word address, byte write masks and fixed read latency."""
from collections import deque,Counter
from dataclasses import dataclass,replace
import random
from .apb import ProtocolError


@dataclass(frozen=True)
class Config:
    depth:int=16
    latency:int=1
    readonly:bool=False
    initial:tuple=()
    def __post_init__(self):
        if self.depth<1 or self.latency<1:raise ValueError('memory depth or read latency')
        if len(self.initial)>self.depth or any(not 0<=x<2**32 for x in self.initial):raise ValueError('memory initial words')


@dataclass(frozen=True)
class Pins:
    reset_n:int=1
    enable:int=0
    write:int=0
    address:int=0
    data:int=0
    mask:int=15
    valid:int=0
    response:int=0


class Reference:
    """Reset cancels reads and restores the declared initial image."""
    def __init__(self,config=Config()):self.config=config;self.reset()
    def reset(self):
        c=self.config;self.memory=list(c.initial)+[0]*(c.depth-len(c.initial));self.pending=deque([None]*c.latency)
    def step(self,p):
        if not p.reset_n:self.reset();return replace(p,valid=0,response=0)
        value=None
        if p.enable:
            if not 0<=p.address<self.config.depth:raise ProtocolError('MEM_ADDRESS')
            if p.write not in (0,1) or not 0<=p.data<2**32 or not 0<=p.mask<16:raise ProtocolError('MEM_PROFILE')
            if p.write:
                if self.config.readonly:raise ProtocolError('MEM_ROM_WRITE')
                for i in range(4):
                    if p.mask>>i&1:self.memory[p.address]=(self.memory[p.address]&~(255<<(8*i)))|(p.data&(255<<(8*i)))
            else:value=self.memory[p.address]
        self.pending.append(value);value=self.pending.popleft()
        return replace(p,valid=int(value is not None),response=value or 0)


class Monitor:
    def __init__(self,hook=lambda p:None,config=Config()):
        self.reference=Reference(config);self.hook=hook;self.coverage=Counter()
    def sample(self,p):
        expected=self.reference.step(p)
        if p.valid!=expected.valid or p.valid and p.response!=expected.response:raise ProtocolError('MEM_READ_DATA_OR_LATENCY')
        if p.enable:self.coverage['write' if p.write else 'read']+=1
        if p.valid:self.coverage['response']+=1;self.hook(p)
    def finish(self):
        if any(x is not None for x in self.reference.pending):raise ProtocolError('MEM_MISSING_READ')
        if not self.coverage['response']:raise ProtocolError('MEM_NO_READS')


class Manager:
    def __init__(self,tick,config=Config()):self.tick=tick;self.config=config
    def write(self,address,data,mask=15):self.tick(Pins(enable=1,write=1,address=address,data=data,mask=mask))
    def read(self,address):
        self.tick(Pins(enable=1,address=address))
        for _ in range(self.config.latency):p=self.tick(Pins())
        if not p.valid:raise ProtocolError('MEM_MISSING_READ')
        return p.response


class Scoreboard(Monitor):
    def observe(self,p):self.sample(p)


def sequences(seed=1,count=16,config=Config()):
    rng=random.Random(seed)
    for _ in range(count):
        address=rng.randrange(config.depth)
        if not config.readonly:yield Pins(enable=1,write=1,address=address,data=rng.getrandbits(32),mask=rng.randrange(16))
        yield Pins(enable=1,address=address)
    for _ in range(config.latency):yield Pins()


class CocotbAgent:
    def __init__(self,dut,prefix,config=Config(),hook=lambda p:None):
        self.dut,self.prefix=dut,prefix;self.monitor=Monitor(hook,config)
    def signal(self,k):return getattr(self.dut,self.prefix+'_'+k)
    async def drive(self,p):
        from cocotb.triggers import FallingEdge,RisingEdge
        await FallingEdge(self.dut.clk)
        self.dut.reset_n.value=p.reset_n
        for k in ('enable','write','address','data','mask'):self.signal(k).value=getattr(p,k)
        await RisingEdge(self.dut.clk)
        out=replace(p,valid=int(self.signal('valid').value),response=int(self.signal('response').value))
        self.monitor.sample(out);return out
