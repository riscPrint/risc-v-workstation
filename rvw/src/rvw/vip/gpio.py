"""GPIO sampled reference. One sample per clock, before DUT updates."""
from collections import Counter, deque
from dataclasses import dataclass, replace
import random
from .apb import ProtocolError, NoChecks


@dataclass(frozen=True)
class Config:
    width: int = 8
    sync_cycles: int = 2
    rising: int = 0
    falling: int = 0
    high: int = 0
    low: int = 0
    def __post_init__(self):
        if not 1 <= self.width <= 32 or self.sync_cycles < 0: raise ValueError('GPIO width or latency')
        if any(x < 0 or x >= 1 << self.width for x in (self.rising,self.falling,self.high,self.low)):
            raise ValueError('GPIO interrupt mask')


@dataclass(frozen=True)
class Pins:
    reset_n: int = 1
    external: int = 0
    direction: int = 0
    output: int = 0
    sampled: int = 0
    irq: int = 0


class Reference:
    """direction=1 selects output. IRQ is per-pin, non-latching.

    Input is sampled after sync_cycles previous sample calls. Output pins
    feed back through the same synchronizer. Reset clears pipeline and IRQ.
    """
    def __init__(self, config=Config()): self.config=config; self.reset()
    def reset(self):
        self.pipe=deque([0]*self.config.sync_cycles); self.previous=0
    def step(self,p):
        c=self.config; mask=(1<<c.width)-1
        if not p.reset_n: self.reset(); return replace(p,sampled=0,irq=0)
        if any(type(v) not in (int,bool) or v < 0 or v > mask for v in (p.external,p.direction,p.output)):
            raise ProtocolError('GPIO_UNKNOWN_OR_WIDE_PIN')
        value=((p.output&p.direction)|(p.external&~p.direction))&mask
        self.pipe.append(value); value=self.pipe.popleft()
        irq=((value&~self.previous&c.rising)|(~value&self.previous&c.falling)|
             (value&c.high)|(~value&c.low))&mask
        self.previous=value
        return replace(p,sampled=value,irq=irq)


class Monitor:
    def __init__(self,hook=lambda pins:None,config=Config()):
        self.reference=Reference(config); self.hook=hook; self.coverage=Counter(); self.previous=Pins()
    def sample(self,p):
        expected=self.reference.step(p)
        if (p.sampled,p.irq)!=(expected.sampled,expected.irq): raise ProtocolError('GPIO_STATE_OR_IRQ')
        self.coverage['samples']+=1
        if p.direction!=self.previous.direction: self.coverage['direction_change']+=1
        if p.irq: self.coverage['interrupt']+=1
        if not p.reset_n: self.coverage['reset']+=1
        self.previous=p; self.hook(p)


class Manager:
    def __init__(self,tick,config=Config()): self.tick=tick; self.monitor=Monitor(config=config)
    def drive(self,p):
        observed=self.tick(p); self.monitor.sample(observed); return observed


class Scoreboard(Monitor):
    def observe(self,p): self.sample(p)
    def finish(self):
        if not self.coverage['samples']: raise NoChecks('GPIO_NO_SAMPLES')


def sequences(seed=1,count=32,config=Config()):
    rng=random.Random(seed); mask=(1<<config.width)-1
    return [Pins(reset_n=0),Pins(external=mask),Pins(direction=mask,output=mask)]+[
        Pins(external=rng.getrandbits(config.width),direction=rng.getrandbits(config.width),
             output=rng.getrandbits(config.width)) for _ in range(count)]


def inject(p): return replace(p,irq=p.irq^1)


class CocotbAgent:
    def __init__(self,dut,prefix,config=Config()):
        self.dut,self.prefix=dut,prefix; self.monitor=Monitor(config=config)
    def signal(self,name): return getattr(self.dut,self.prefix+'_'+name)
    async def drive(self,p):
        from cocotb.triggers import FallingEdge,RisingEdge,ReadOnly
        await FallingEdge(self.dut.clk)
        self.dut.reset_n.value=p.reset_n
        for k in ('external','direction','output'): self.signal(k).value=getattr(p,k)
        await RisingEdge(self.dut.clk)
        # Sample before sequential updates, as required by the cycle contract.
        try: observed=replace(p, sampled=int(self.signal('sampled').value),irq=int(self.signal('irq').value))
        except ValueError as exc: raise ProtocolError('GPIO_UNKNOWN_OR_WIDE_PIN') from exc
        self.monitor.sample(observed)
        await ReadOnly()
        return observed
