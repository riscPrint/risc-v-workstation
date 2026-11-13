"""Sampled interrupt lines. No interrupt controller or CPU semantics."""
from collections import Counter,deque
from dataclasses import dataclass
import random
from .apb import ProtocolError


@dataclass(frozen=True)
class Event:
    levels:int
    cycles:int=1


class Monitor:
    def __init__(self,hook=lambda event:None,width=8,min_pulse=1):
        if not 1<=width<=64 or min_pulse<1:raise ValueError('interrupt width or pulse length')
        self.width,self.min_pulse,self.hook=width,min_pulse,hook
        self.coverage=Counter();self.previous=0;self.lengths=[0]*width
    def sample(self,levels,reset_n=True):
        if not reset_n:self.previous=0;self.lengths=[0]*self.width;self.coverage['reset']+=1;return
        if type(levels) not in (int,bool) or not 0<=levels<1<<self.width:raise ProtocolError('IRQ_UNKNOWN_OR_WIDE')
        for i in range(self.width):
            if levels>>i&1:self.lengths[i]+=1
            elif self.previous>>i&1:
                if self.lengths[i]<self.min_pulse:raise ProtocolError('IRQ_SHORT_PULSE')
                self.coverage[('pulse',i,self.lengths[i])]+=1;self.lengths[i]=0
        if levels!=self.previous:
            self.hook(Event(levels));self.coverage['edges']+=(levels^self.previous).bit_count()
        self.previous=levels;self.coverage['samples']+=1
    def finish(self):
        if any(0<n<self.min_pulse for n in self.lengths):raise ProtocolError('IRQ_SHORT_PULSE')
        if not self.coverage['samples']:raise ProtocolError('IRQ_NO_SAMPLES')


class Scoreboard:
    def __init__(self):self.expected=deque();self.count=0
    def expect(self,event):
        if event.cycles<1:raise ValueError('interrupt duration')
        self.expected.extend([event.levels]*event.cycles)
    def sample(self,levels):
        if not self.expected or self.expected.popleft()!=levels:raise ProtocolError('IRQ_LEVEL_OR_TIMING')
        self.count+=1
    def finish(self):
        if self.expected or not self.count:raise ProtocolError('IRQ_MISSING_SAMPLES')


class Manager:
    def __init__(self,tick,width=8):self.tick=tick;self.monitor=Monitor(width=width)
    def send(self,event):
        if event.cycles<1:raise ValueError('interrupt duration')
        for _ in range(event.cycles):
            observed=self.tick(event.levels);self.monitor.sample(observed)
            if observed!=event.levels:raise ProtocolError('IRQ_DRIVE_MISMATCH')


def sequences(seed=1,count=16,width=8):
    rng=random.Random(seed)
    return [Event(0),Event((1<<width)-1,2),Event(0)]+[
        Event(rng.getrandbits(width),rng.randrange(1,5)) for _ in range(count)]+[Event(0)]


class CocotbAgent:
    def __init__(self,dut,signal='irq',width=8,min_pulse=1):
        self.dut,self.signal=dut,signal;self.monitor=Monitor(width=width,min_pulse=min_pulse)
    async def send(self,event):
        from cocotb.triggers import FallingEdge,RisingEdge
        if event.cycles<1:raise ValueError('interrupt duration')
        await FallingEdge(self.dut.clk);getattr(self.dut,self.signal).value=event.levels
        for _ in range(event.cycles):
            await RisingEdge(self.dut.clk)
            self.monitor.sample(int(getattr(self.dut,self.signal).value),int(self.dut.reset_n.value))
    async def run_monitor(self):
        from cocotb.triggers import RisingEdge
        while True:
            await RisingEdge(self.dut.clk)
            self.monitor.sample(int(getattr(self.dut,self.signal).value),int(self.dut.reset_n.value))
