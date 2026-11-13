"""Bounded TileLink-UL/UH A/D agents. 32-bit data/address, 4-bit source.

UH supports up to 64-byte messages. Atomics are at most one data beat.
No coherent B/C/E channels. All methods accept explicit immutable pin samples.
"""
from collections import Counter, deque
from dataclasses import dataclass, replace
import random
from .apb import ProtocolError, completion


@dataclass(frozen=True)
class Request:
    opcode: int = 4
    param: int = 0
    size: int = 2
    source: int = 0
    address: int = 0
    mask: int = 15
    data: int = 0
    corrupt: bool = False


@dataclass(frozen=True)
class Response:
    opcode: int = 1
    param: int = 0
    size: int = 2
    source: int = 0
    data: int = 0
    denied: bool = False
    corrupt: bool = False
    sink: int = 0


@dataclass(frozen=True)
class Pins:
    reset_n: int = 1
    a_valid: int = 0
    a_ready: int = 0
    a: Request = Request()
    d_valid: int = 0
    d_ready: int = 0
    d: Response = Response()


def beats(size): return max(1, (1 << size)//4)
def a_beats(a): return beats(a.size) if a.opcode in (0,1,2,3) else 1
def d_opcode(a): return 1 if a.opcode in (2,3,4) else 2 if a.opcode==5 else 0
def d_beats(a): return beats(a.size) if d_opcode(a)==1 else 1

def check_request(a, uh=False):
    if not (0<=a.address<2**32 and 0<=a.source<16 and 0<=a.size<=(6 if uh else 2)
            and a.opcode in ((0,1,2,3,4,5) if uh else (0,1,4)) and 0<=a.data<2**32
            and 0<=a.mask<16):
        raise ProtocolError('TL_PROFILE')
    if a.address % (1 << a.size): raise ProtocolError('TL_ALIGNMENT')
    lane_mask = 15 if a.size>=2 else ((1 << (1 << a.size))-1) << (a.address%4)
    if a.mask & ~lane_mask or a.opcode!=1 and a.mask!=lane_mask:
        raise ProtocolError('TL_MASK')
    if a.opcode==2 and (a.param not in range(5) or a.size>2) or \
       a.opcode==3 and (a.param not in range(4) or a.size>2) or \
       a.opcode==5 and a.param not in (0,1) or a.opcode in (0,1,4) and a.param:
        raise ProtocolError('TL_PARAM')
    if a.corrupt and a.opcode not in (0,1,2,3): raise ProtocolError('TL_A_CORRUPT')


class Monitor:
    """Track message boundaries and source allocation, including same-edge D."""
    def __init__(self, hook=lambda event: None, uh=False):
        self.hook,self.uh=hook,uh
        self.pending={}
        self.a_active=self.d_active=None
        self.coverage=Counter();self.completed=0

    def sample(self,p):
        if not p.reset_n:
            self.pending.clear(); self.a_active=self.d_active=None
            self.coverage['reset']+=1
            return
        # TileLink permits a sender to change an unaccepted single beat.
        # Check message control across accepted beats, not AXI stall stability.
        if p.a_valid:
            check_request(p.a,self.uh)
            if not p.a_ready: self.coverage['a_stall']+=1
        if p.a_valid and p.a_ready:
            a=p.a
            if self.a_active is None:
                if a.source in self.pending: raise ProtocolError('TL_SOURCE_REUSE')
                self.pending[a.source]={'a':a,'requests':[],'responses':[],'a_done':False,'d_done':False}
                self.a_active=a.source
            state=self.pending[self.a_active]; first=state['a']
            if (a.opcode,a.param,a.size,a.source,a.address)!=(first.opcode,first.param,first.size,first.source,first.address):
                raise ProtocolError('TL_A_MESSAGE_CONTROL')
            state['requests'].append(a)
            self.coverage[('request',a.opcode,a.param,a.size)]+=1
            if len(state['requests'])==a_beats(first):
                state['a_done']=True; self.a_active=None
        if p.d_valid and not p.d_ready: self.coverage['d_stall']+=1
        if p.d_valid:
            d=p.d
            if d.source not in self.pending:
                if not p.a_valid or p.a.source!=d.source or self.a_active is not None:
                    raise ProtocolError('TL_D_WITHOUT_A')
                if p.d_ready: raise ProtocolError('TL_D_BEFORE_A')
                state={'a':p.a,'responses':[],'d_done':False}
            else:
                state=self.pending[d.source]
            a=state['a']
            if state['d_done']: raise ProtocolError('TL_EXTRA_D')
            if self.d_active is not None and self.d_active!=d.source: raise ProtocolError('TL_D_INTERLEAVE')
            if d.opcode!=d_opcode(a) or d.size!=a.size or d.param or d.sink:
                raise ProtocolError('TL_D_CONTROL')
            if not 0<=d.data<2**32: raise ProtocolError('TL_D_WIDTH')
            if d.corrupt and d.opcode!=1 or d.denied and d.opcode==1 and not d.corrupt:
                raise ProtocolError('TL_D_CORRUPT')
            if state['responses'] and d.denied!=state['responses'][0].denied:
                raise ProtocolError('TL_DENIED_MESSAGE')
            if p.d_ready:
                state['responses'].append(d)
                self.d_active=d.source
                self.coverage[('response',d.opcode,d.denied,d.corrupt)]+=1
                if len(state['responses'])==d_beats(a):
                    state['d_done']=True; self.d_active=None
        for source,state in list(self.pending.items()):
            if state['a_done'] and state['d_done']:
                self.hook((tuple(state['requests']),tuple(state['responses'])))
                del self.pending[source]
                self.completed+=1

    def finish(self, *, idle_reason=None):
        if self.pending: raise ProtocolError('TL_OUTSTANDING')
        return completion(self.completed, idle_reason)


class Memory:
    """Independent byte-memory transaction model. Atomics return old data."""
    def __init__(self): self.bytes={}

    def execute(self,requests):
        a=requests[0]; result=[]
        if len(requests)!=a_beats(a): raise ProtocolError('TL_A_LENGTH')
        for i in range(d_beats(a)):
            base=(a.address & ~3)+4*i
            data=sum(self.bytes.get(base+j,0)<<(8*j) for j in range(4))
            result.append(Response(d_opcode(a),size=a.size,source=a.source,data=data if d_opcode(a)==1 else 0))
        if any(r.corrupt for r in requests):
            return tuple(replace(d,denied=True,corrupt=d.opcode==1) for d in result)
        if a.opcode in (0,1):
            for i,r in enumerate(requests):
                base=(a.address & ~3)+4*i
                for lane in range(4):
                    if r.mask>>lane&1: self.bytes[base+lane]=(r.data>>(8*lane))&255
        elif a.opcode in (2,3):
            width=8*(1<<a.size); mask=(1<<width)-1; shift=8*(a.address%4)
            old=(result[0].data>>shift)&mask; operand=(a.data>>shift)&mask
            signed=lambda v: v-(1<<width) if v>>(width-1) else v
            if a.opcode==2:
                new=(min((old,operand),key=signed),max((old,operand),key=signed),
                     min(old,operand),max(old,operand),old+operand)[a.param]
            else: new=(old^operand,old|operand,old&operand,operand)[a.param]
            for i in range(1<<a.size): self.bytes[a.address+i]=(new>>(8*i))&255
        return tuple(result)


class Scoreboard:
    """For serial fixtures. Concurrent memory order needs a project policy."""
    def __init__(self): self.model=Memory(); self.count=0
    def observe(self,event):
        requests,responses=event
        if tuple(responses)!=self.model.execute(requests): raise ProtocolError('TL_MEMORY_DATA')
        self.count+=1
    def finish(self):
        if not self.count: raise ProtocolError('TL_NO_TRAFFIC')


class Subordinate:
    """Seeded reactive RAM. Holds each D beat; never interleaves a D message."""
    def __init__(self,seed=1,buggy=False):
        self.seed,self.buggy=seed,buggy; self.rng=random.Random(seed)
        self.model=Memory(); self.requests=[]; self.messages=[]; self.active=deque()
    def step(self,p,commit=True,driven=None):
        if not p.reset_n:
            self.__init__(self.seed,self.buggy); return Pins(reset_n=0)
        if not self.active and self.messages:
            self.active.extend(self.messages.pop(self.rng.randrange(len(self.messages))))
        out=replace(p,a_ready=int(self.rng.randrange(4)!=0),d_valid=int(bool(self.active)),
                    d=self.active[0] if self.active else Response())
        if driven is not None: out=replace(out,a_ready=driven.a_ready)
        if not commit: return out
        if out.d_valid and p.d_ready: self.active.popleft()
        if p.a_valid and out.a_ready:
            check_request(p.a,True); self.requests.append(p.a)
            if len(self.requests)==a_beats(self.requests[0]):
                response=self.model.execute(self.requests)
                if self.buggy: response=tuple(replace(d,data=d.data^1) if d.opcode==1 else d for d in response)
                self.messages.append(response); self.requests=[]
        return out


class Manager:
    def __init__(self,tick,timeout=1000): self.tick,self.timeout=tick,timeout
    def transfer(self,requests):
        requests=tuple(requests)
        if not requests or len(requests)!=a_beats(requests[0]): raise ValueError('request length')
        index=0; responses=[]
        for _ in range(self.timeout):
            p=self.tick(Pins(a_valid=int(index<len(requests)),a=requests[min(index,len(requests)-1)],d_ready=1))
            if not p.reset_n: return None
            if index<len(requests) and p.a_ready: index+=1
            if p.d_valid:
                responses.append(p.d)
            if index==len(requests) and len(responses)==d_beats(requests[0]): return tuple(responses)
        raise TimeoutError('TileLink test policy timeout')


def sequences(seed=1,uh=False):
    rng=random.Random(seed)
    for size in range(7 if uh else 3):
        mask=15 if size>=2 else (1<<(1<<size))-1
        for opcode in (0,1,4):
            a=Request(opcode,size=size,address=0x100,mask=mask,source=rng.randrange(16))
            yield tuple(replace(a,data=rng.getrandbits(32)) for _ in range(a_beats(a)))
    if uh:
        for opcode,params in ((2,range(5)),(3,range(4)),(5,range(2))):
            for param in params: yield (Request(opcode,param,address=0x100,data=rng.getrandbits(32)),)


def inject(p,fault='source'):
    if fault=='source': return replace(p,d=replace(p.d,source=p.d.source^1))
    if fault=='mask': return replace(p,a=replace(p.a,mask=0))
    if fault=='data': return replace(p,d=replace(p.d,data=p.d.data^1))
    raise ValueError(fault)


class CocotbAgent:
    def __init__(self,dut,prefix,hook=lambda event:None,uh=False):
        self.dut,self.prefix=dut,prefix; self.monitor=Monitor(hook,uh)
    def signal(self,name): return getattr(self.dut,self.prefix+'_'+name)
    def pins(self):
        values={'reset_n':int(self.dut.reset_n.value)}
        for ch,cls in (('a',Request),('d',Response)):
            for suffix in ('valid','ready'): values[ch+'_'+suffix]=int(self.signal(ch+'_'+suffix).value)
            values[ch]=cls(**{field:int(self.signal(ch+'_'+field).value) for field in cls.__dataclass_fields__})
        return Pins(**values)
    def drive(self,p,subordinate=False):
        for ch in ('a','d'):
            output=(ch=='d')==subordinate
            suffix='valid' if output else 'ready'
            self.signal(ch+'_'+suffix).value=getattr(p,ch+'_'+suffix)
            if output:
                for field,value in vars(getattr(p,ch)).items(): self.signal(ch+'_'+field).value=int(value)
    async def run_monitor(self):
        from cocotb.triggers import RisingEdge
        while True:
            await RisingEdge(self.dut.clk); self.monitor.sample(self.pins())
    async def run_subordinate(self,seed=1):
        from cocotb.triggers import RisingEdge,FallingEdge
        model=Subordinate(seed)
        while True:
            await FallingEdge(self.dut.clk)
            p=model.step(self.pins(),commit=False); self.drive(p,True)
            await RisingEdge(self.dut.clk); model.step(self.pins(),driven=p)
    async def transfer(self,requests,timeout=1000):
        from cocotb.triggers import RisingEdge,FallingEdge
        requests=tuple(requests)
        if not requests or len(requests)!=a_beats(requests[0]): raise ValueError('request length')
        index=0; result=[]
        for _ in range(timeout):
            await FallingEdge(self.dut.clk)
            self.drive(Pins(a_valid=int(index<len(requests)),a=requests[min(index,len(requests)-1)],d_ready=1))
            await RisingEdge(self.dut.clk); p=self.pins()
            if not p.reset_n: break
            if index<len(requests) and p.a_ready: index+=1
            if p.d_valid:
                result.append(p.d)
            if index==len(requests) and len(result)==d_beats(requests[0]): break
        else: raise TimeoutError('TileLink cocotb policy timeout')
        await FallingEdge(self.dut.clk); self.drive(Pins())
        return tuple(result)
