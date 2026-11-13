"""Single-select four-wire SPI cycle agents. No in-band backpressure."""
from collections import Counter,deque
from dataclasses import dataclass,replace
import random
from .apb import ProtocolError


@dataclass(frozen=True)
class Config:
    polarity:int=0
    phase:int=0
    bits:int=8
    lsb_first:bool=False
    def __post_init__(self):
        if self.polarity not in (0,1) or self.phase not in (0,1) or not 1<=self.bits<=32:
            raise ValueError('SPI mode or word width')


@dataclass(frozen=True)
class Pins:
    reset_n:int=1
    cs_n:int=1
    sclk:int=0
    mosi:int=0
    miso:int=0


@dataclass(frozen=True)
class Word:
    mosi:int
    miso:int


def sampling(old,p,c):
    return old.sclk!=p.sclk and p.sclk==(c.polarity if c.phase else 1-c.polarity)


def waveform(word,config=Config()):
    c=config
    if not 0<=word<1<<c.bits: raise ValueError('SPI word width')
    yield Pins(cs_n=0,sclk=c.polarity)
    for i in range(c.bits):
        bit=(word>>(i if c.lsb_first else c.bits-1-i))&1
        # Set up data before the leading edge, including CPHA=0.
        yield Pins(cs_n=0,sclk=c.polarity,mosi=bit)
        yield Pins(cs_n=0,sclk=1-c.polarity,mosi=bit)
        yield Pins(cs_n=0,sclk=c.polarity,mosi=bit)
    yield Pins(sclk=c.polarity)


class Monitor:
    def __init__(self,hook=lambda word:None,config=Config()):
        self.hook,self.config=hook,config; self.coverage=Counter(); self.reset()
    def reset(self):
        self.previous=Pins(reset_n=0,sclk=self.config.polarity)
        self.count=self.tx=self.rx=0
    def sample(self,p):
        c=self.config; old,self.previous=self.previous,p
        if not p.reset_n: self.reset(); self.coverage['reset']+=1; return
        if any(v not in (0,1) for v in (p.cs_n,p.sclk,p.mosi,p.miso)): raise ProtocolError('SPI_UNKNOWN_PIN')
        if p.cs_n:
            if p.sclk!=c.polarity: raise ProtocolError('SPI_IDLE_CLOCK')
            if not old.cs_n and self.count: raise ProtocolError('SPI_PARTIAL_WORD')
            return
        if old.cs_n:
            if p.sclk!=c.polarity: raise ProtocolError('SPI_SELECT_CLOCK')
            self.count=self.tx=self.rx=0
        if sampling(old,p,c):
            index=self.count if c.lsb_first else c.bits-1-self.count
            self.tx|=p.mosi<<index; self.rx|=p.miso<<index; self.count+=1
            if self.count==c.bits:
                self.hook(Word(self.tx,self.rx)); self.coverage['words']+=1
                self.coverage[('mode',c.polarity,c.phase,c.bits)]+=1
                self.count=self.tx=self.rx=0
    def finish(self):
        if self.count or not self.previous.cs_n: raise ProtocolError('SPI_UNFINISHED_SELECT')


class Subordinate:
    """Reactive MISO serializer. Queue empty policy: return all ones."""
    def __init__(self,words=(),config=Config(),buggy=False):
        self.words=deque(words); self.config=config; self.buggy=buggy
        self.previous=Pins(sclk=config.polarity); self.index=0; self.word=0
    def step(self,p):
        c=self.config
        if not p.reset_n:
            self.index=0; self.previous=Pins(sclk=c.polarity); return replace(p,miso=0)
        old,self.previous=self.previous,p
        if p.cs_n: self.index=0; return replace(p,miso=0)
        if old.cs_n or self.index==0:
            self.word=self.words[0] if self.words else (1<<c.bits)-1
            if not 0<=self.word<1<<c.bits: raise ValueError('SPI response width')
            self.index=0
        bit=(self.word>>(self.index if c.lsb_first else c.bits-1-self.index))&1
        if self.buggy: bit^=1
        out=replace(p,miso=bit)
        if sampling(old,p,c):
            self.index+=1
            if self.index==c.bits:
                if self.words: self.words.popleft()
                self.index=0
        return out


class Manager:
    def __init__(self,tick,config=Config()): self.tick,self.config=tick,config
    def transfer(self,word):
        result=[]; mon=Monitor(result.append,self.config)
        for p in waveform(word,self.config): mon.sample(self.tick(p))
        mon.finish()
        if len(result)!=1: raise ProtocolError('SPI_MISSING_WORD')
        return result[0].miso


class Scoreboard:
    def __init__(self): self.expected=deque(); self.count=0
    def expect(self,word): self.expected.append(word)
    def observe(self,word):
        if not self.expected or self.expected.popleft()!=word: raise ProtocolError('SPI_WORD_STREAM')
        self.count+=1
    def finish(self):
        if self.expected or not self.count: raise ProtocolError('SPI_MISSING_WORD')


def sequences(seed=1,count=32,config=Config()):
    rng=random.Random(seed)
    return [0,(1<<config.bits)-1]+[rng.getrandbits(config.bits) for _ in range(count)]


def inject(p,fault='select'):
    if fault=='select': return replace(p,cs_n=1)
    if fault=='data': return replace(p,mosi=p.mosi^1)
    if fault=='clock': return replace(p,sclk=p.sclk^1)
    raise ValueError(fault)


class CocotbAgent:
    """DUT pins: PREFIX_cs_n/sclk/mosi/miso; simulation clock: clk."""
    def __init__(self,dut,prefix,config=Config(),hook=lambda word:None):
        self.dut,self.prefix,self.config=dut,prefix,config; self.monitor=Monitor(hook,config)
    def signal(self,name): return getattr(self.dut,self.prefix+'_'+name)
    def pins(self):
        return Pins(int(self.dut.reset_n.value),*[int(self.signal(k).value) for k in ('cs_n','sclk','mosi','miso')])
    async def transfer(self,word):
        from cocotb.triggers import FallingEdge,RisingEdge,ClockCycles
        result=[]; mon=Monitor(result.append,self.config)
        for p in waveform(word,self.config):
            await FallingEdge(self.dut.clk)
            for name in ('cs_n','sclk','mosi'): self.signal(name).value=getattr(p,name)
            await RisingEdge(self.dut.clk); observed=self.pins(); mon.sample(observed)
            if not observed.reset_n: return None
            await ClockCycles(self.dut.clk,2)
        mon.finish(); return result[0].miso
    async def run_monitor(self):
        from cocotb.triggers import RisingEdge
        while True:
            await RisingEdge(self.dut.clk); self.monitor.sample(self.pins())
    async def run_subordinate(self,words=()):
        # Drive MISO between SPI sample edges. The integration must supply at
        # least two simulation clock edges per SCLK half-period.
        from cocotb.triggers import FallingEdge
        model=Subordinate(words,self.config)
        while True:
            await FallingEdge(self.dut.clk)
            self.signal('miso').value=model.step(self.pins()).miso
