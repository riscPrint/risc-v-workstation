"""Wishbone Classic, byte-addressed 32-bit profile. No pipelined cycles."""
from collections import Counter
from dataclasses import dataclass,replace
import random
from .apb import ProtocolError, completion


@dataclass(frozen=True)
class Pins:
    reset_n:int=1
    cyc:int=0
    stb:int=0
    we:int=0
    adr:int=0
    dat_w:int=0
    sel:int=15
    ack:int=0
    err:int=0
    dat_r:int=0


@dataclass(frozen=True)
class Transfer:
    address:int
    write:bool=False
    data:int=0
    select:int=15
    response:int=0
    error:bool=False


class Monitor:
    def __init__(self,hook=lambda transfer:None): self.hook=hook;self.pending=None;self.coverage=Counter()
    def sample(self,p):
        if not p.reset_n: self.pending=None;self.coverage['reset']+=1;return
        if any(v not in (0,1) for v in (p.cyc,p.stb,p.we,p.ack,p.err)):
            raise ProtocolError('WB_UNKNOWN_PIN')
        if p.ack and p.err: raise ProtocolError('WB_MULTIPLE_TERMINATION')
        if p.stb and not p.cyc: raise ProtocolError('WB_STROBE_WITHOUT_CYCLE')
        active=p.cyc and p.stb
        control=(p.we,p.adr,p.dat_w,p.sel)
        if self.pending is not None and (not active or control!=self.pending):
            raise ProtocolError('WB_UNSTABLE_REQUEST')
        if active:
            if p.adr%4 or not 0<=p.adr<2**32 or not 0<=p.sel<16 or not 0<=p.dat_w<2**32:
                raise ProtocolError('WB_PROFILE')
            if p.ack or p.err:
                self.hook(Transfer(p.adr,bool(p.we),p.dat_w,p.sel,p.dat_r,bool(p.err)))
                self.coverage['error' if p.err else 'transfer']+=1;self.pending=None
            else: self.pending=control;self.coverage['wait']+=1
        elif p.ack or p.err: raise ProtocolError('WB_UNSOLICITED_RESPONSE')
    def finish(self, *, idle_reason=None):
        if self.pending is not None: raise ProtocolError('WB_UNFINISHED')
        return completion(self.coverage['transfer']+self.coverage['error'], idle_reason)


class Subordinate:
    def __init__(self,seed=1,depth=16,buggy=False):
        self.rng=random.Random(seed);self.memory=[0]*depth;self.remaining=None;self.buggy=buggy
    def step(self,p):
        if not p.reset_n:
            self.memory[:]=[0]*len(self.memory);self.remaining=None;return replace(p,ack=0,err=0,dat_r=0)
        if not(p.cyc and p.stb): self.remaining=None;return replace(p,ack=0,err=0,dat_r=0)
        if self.remaining is None:self.remaining=self.rng.randrange(4)
        if self.remaining:self.remaining-=1;return replace(p,ack=0,err=0)
        error=p.adr%4!=0 or not 0<=p.adr//4<len(self.memory)
        data=0 if error else self.memory[p.adr//4]
        if p.we and not error:
            for i in range(4):
                if p.sel>>i&1:self.memory[p.adr//4]=(self.memory[p.adr//4]&~(255<<(8*i)))|(p.dat_w&(255<<(8*i)))
        self.remaining=None
        return replace(p,ack=int(not error),err=int(error),dat_r=data^int(self.buggy))


class Manager:
    def __init__(self,tick,timeout=100):self.tick=tick;self.timeout=timeout
    def transfer(self,t):
        p=Pins(cyc=1,stb=1,we=int(t.write),adr=t.address,dat_w=t.data,sel=t.select)
        for _ in range(self.timeout):
            got=self.tick(p)
            if not got.reset_n:raise ProtocolError('WB_RESET_ABORT')
            if got.ack or got.err:
                self.tick(Pins());return replace(t,response=got.dat_r,error=bool(got.err))
        raise TimeoutError('Wishbone timeout (test policy)')


class Scoreboard:
    def __init__(self,depth=16):self.memory=[0]*depth;self.count=0
    def observe(self,t):
        error=not 0<=t.address//4<len(self.memory)
        if t.error!=error:raise ProtocolError('WB_ERROR_RESPONSE')
        if not error:
            old=self.memory[t.address//4]
            if not t.write and t.response!=old:raise ProtocolError('WB_READ_DATA')
            if t.write:
                for i in range(4):
                    if t.select>>i&1:old=(old&~(255<<(i*8)))|(t.data&(255<<(i*8)))
                self.memory[t.address//4]=old
        self.count+=1
    def finish(self):
        if not self.count:raise ProtocolError('WB_NO_TRANSFERS')


def sequences(seed=1,count=16):
    rng=random.Random(seed)
    for _ in range(count):
        addr=rng.randrange(16)*4
        yield Transfer(addr,True,rng.getrandbits(32),rng.randrange(16))
        yield Transfer(addr)
    yield Transfer(64)


class CocotbAgent:
    def __init__(self,dut,prefix,hook=lambda t:None,timeout=100):
        self.dut,self.prefix,self.timeout=dut,prefix,timeout;self.monitor=Monitor(hook)
    def signal(self,k):return getattr(self.dut,self.prefix+'_'+k)
    def pins(self):return Pins(int(self.dut.reset_n.value),*[int(self.signal(k).value) for k in list(Pins.__dataclass_fields__)[1:]])
    async def transfer(self,t):
        from cocotb.triggers import FallingEdge,RisingEdge
        await FallingEdge(self.dut.clk)
        for k,v in dict(cyc=1,stb=1,we=int(t.write),adr=t.address,dat_w=t.data,sel=t.select).items():self.signal(k).value=v
        for _ in range(self.timeout):
            await RisingEdge(self.dut.clk);p=self.pins();self.monitor.sample(p)
            if not p.reset_n:raise ProtocolError('WB_RESET_ABORT')
            if p.ack or p.err:break
        else:raise TimeoutError('Wishbone timeout (test policy)')
        await FallingEdge(self.dut.clk);self.signal('cyc').value=0;self.signal('stb').value=0
        return replace(t,response=p.dat_r,error=bool(p.err))
