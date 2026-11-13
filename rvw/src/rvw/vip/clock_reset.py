"""Integer-time clock/reset stimulus and digital timing checks."""
from collections import Counter
from dataclasses import dataclass
from .apb import ProtocolError


@dataclass(frozen=True)
class Config:
    half_period:int=5
    reset_cycles:int=2
    def __post_init__(self):
        if self.half_period<1 or self.reset_cycles<1:raise ValueError('clock/reset timing')


@dataclass(frozen=True)
class Pins:
    time:int
    clock:int
    reset_n:int


def waveform(cycles=16,config=Config()):
    if cycles<=config.reset_cycles:raise ValueError('need active clock cycles after reset')
    yield Pins(0,0,0)
    for i in range(cycles):
        yield Pins((2*i+1)*config.half_period,1,int(i>=config.reset_cycles))
        yield Pins((2*i+2)*config.half_period,0,int(i+1>=config.reset_cycles))


class Monitor:
    def __init__(self,config=Config(),hook=lambda p:None):
        self.config,self.hook=config,hook;self.previous=None;self.last_edge=None;self.reset_edges=0;self.coverage=Counter()
    def sample(self,p):
        if p.clock not in (0,1) or p.reset_n not in (0,1):raise ProtocolError('CLOCK_RESET_UNKNOWN')
        old=self.previous
        if old and p.time<old.time:raise ProtocolError('CLOCK_TIME_ORDER')
        if old and p.clock!=old.clock:
            if self.last_edge is not None and p.time-self.last_edge!=self.config.half_period:
                raise ProtocolError('CLOCK_HALF_PERIOD')
            self.last_edge=p.time;self.coverage['edges']+=1
            if p.clock and not p.reset_n:self.reset_edges+=1
        elif old is None:self.last_edge=p.time
        if old and old.reset_n and not p.reset_n:self.reset_edges=0;self.coverage['reset_assert']+=1
        if old and not old.reset_n and p.reset_n:
            if p.clock or not old.clock:raise ProtocolError('RESET_RELEASE_EDGE')
            if self.reset_edges<self.config.reset_cycles:raise ProtocolError('RESET_TOO_SHORT')
            self.coverage['reset_release']+=1
        self.previous=p;self.hook(p)
    def finish(self):
        if not self.coverage['edges'] or not self.coverage['reset_release']:raise ProtocolError('CLOCK_RESET_NO_SEQUENCE')
        if self.previous and not self.previous.reset_n:raise ProtocolError('RESET_STILL_ASSERTED')


class Manager:
    def __init__(self,tick,config=Config()):self.tick,self.config=tick,config;self.monitor=Monitor(config)
    def run(self,cycles=16):
        for p in waveform(cycles,self.config):self.monitor.sample(self.tick(p))
        self.monitor.finish()


class Scoreboard(Monitor):
    def observe(self,p):self.sample(p)


class CocotbAgent:
    def __init__(self,dut,clock='clk',reset='reset_n',config=Config()):
        self.dut,self.clock,self.reset,self.config=dut,clock,reset,config;self.monitor=Monitor(config)
    async def run(self,cycles=16):
        from cocotb.triggers import Timer,ReadOnly
        previous=0
        for p in waveform(cycles,self.config):
            if p.time>previous:await Timer(p.time-previous,unit='ns')
            getattr(self.dut,self.clock).value=p.clock;getattr(self.dut,self.reset).value=p.reset_n
            self.monitor.sample(p);previous=p.time
        self.monitor.finish()
