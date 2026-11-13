"""Generic JTAG scans and declared test-access topology. No DMI conformance."""
from collections import Counter
from dataclasses import dataclass,asdict
from rvw.debug.jtag import NEXT,tms_path
from .apb import ProtocolError, completion


@dataclass(frozen=True)
class Tap:
    name:str
    ir_length:int
    tdi:str
    tdo:str
    reset:str
    requirements:tuple=()
    mode:str='test'
    def __post_init__(self):
        if not self.name or not 2<=self.ir_length<=64:raise ValueError('TAP name or instruction length')
        if not all((self.tdi,self.tdo,self.reset,self.mode)):raise ValueError('TAP pins and mode are required')


def topology(taps,connections=None,mode_edges=None,entry='normal'):
    taps=list(taps)
    if not taps or len({t.name for t in taps})!=len(taps):raise ValueError('nonempty unique TAP chain required')
    missing=[]
    if connections is not None:
        edges={tuple(e) for e in connections}
        missing=[(a.tdo,b.tdi) for a,b in zip(taps,taps[1:]) if (a.tdo,b.tdi) not in edges]
    unreachable=[]
    if mode_edges is not None:
        reached={entry}
        while True:
            expanded=reached|{b for a,b in mode_edges if a in reached}
            if expanded==reached:break
            reached=expanded
        unreachable=sorted({t.mode for t in taps}-reached)
    status='mismatch' if missing or unreachable else ('checked' if connections is not None and mode_edges is not None else 'inconclusive')
    return {'schema':'rvw.vip.jtag-topology/1','status':status,'taps':[asdict(t) for t in taps],
            'total_ir_bits':sum(t.ir_length for t in taps),'missing_connections':missing,'unreachable_modes':unreachable,
            'scope':'supplied connectivity and mode graph only; no RISC-V debug conformance'}


@dataclass(frozen=True)
class Pins:
    tck:int=0
    tms:int=1
    tdi:int=0
    tdo:int=0
    trst_n:int=1


class Monitor:
    def __init__(self,hook=lambda state,p:None):self.state='TLR';self.previous=Pins();self.hook=hook;self.coverage=Counter()
    def sample(self,p):
        if any(v not in (0,1) for v in vars(p).values()):raise ProtocolError('JTAG_UNKNOWN_PIN')
        if not p.trst_n:self.state='TLR'
        elif p.tck and not self.previous.tck:
            old=self.state;self.state=NEXT[old][p.tms];self.coverage[(old,self.state)]+=1;self.hook(old,p)
        self.previous=p

    def finish(self, *, idle_reason=None):
        if self.state not in ('TLR', 'RTI'):
            raise ProtocolError('JTAG_UNFINISHED_SCAN')
        return completion(self.coverage[('UPDATE_IR', 'RTI')]+self.coverage[('UPDATE_DR', 'RTI')], idle_reason)


class Manager:
    def __init__(self,tick):self.tick=tick;self.monitor=Monitor()
    def pulse(self,tms,tdi=0):
        self.monitor.sample(self.tick(Pins(tms=tms,tdi=tdi)))
        p=self.tick(Pins(tck=1,tms=tms,tdi=tdi));self.monitor.sample(p)
        self.monitor.sample(self.tick(Pins(tms=tms,tdi=tdi)))
        return p.tdo
    def reset(self):
        for _ in range(5):self.pulse(1)
    def move(self,state):
        for bit in tms_path(self.monitor.state,state):self.pulse(bit)
    def scan(self,value,bits,ir=False):
        if not 1<=bits<=4096 or not 0<=value<1<<bits:raise ValueError('JTAG scan width or value')
        self.move('SHIFT_IR' if ir else 'SHIFT_DR');result=0
        for i in range(bits):result|=self.pulse(int(i==bits-1),(value>>i)&1)<<i
        self.move('RTI');return result


class Scoreboard:
    def __init__(self):self.count=0
    def observe(self,expected,observed):
        if expected!=observed:raise ProtocolError('JTAG_SCAN_DATA')
        self.count+=1
    def finish(self):
        if not self.count:raise ProtocolError('JTAG_NO_SCANS')


class CocotbAgent:
    def __init__(self,dut,prefix='jtag',half_period=5):
        if half_period<1:raise ValueError('JTAG half period')
        self.dut,self.prefix,self.half_period=dut,prefix,half_period;self.monitor=Monitor()
    def signal(self,k):return getattr(self.dut,self.prefix+'_'+k)
    async def pulse(self,tms,tdi=0):
        from cocotb.triggers import Timer
        self.signal('tck').value=0;self.signal('tms').value=tms;self.signal('tdi').value=tdi
        await Timer(self.half_period,unit='ns')
        self.signal('tck').value=1
        await Timer(self.half_period,unit='ns')
        p=Pins(1,tms,tdi,int(self.signal('tdo').value),int(self.signal('trst_n').value))
        self.monitor.sample(Pins(0,tms,tdi,p.tdo,p.trst_n));self.monitor.sample(p)
        self.signal('tck').value=0
        return p.tdo
    async def reset(self):
        for _ in range(5):await self.pulse(1)
    async def scan(self,value,bits,ir=False):
        if not 1<=bits<=4096 or not 0<=value<1<<bits:raise ValueError('JTAG scan width or value')
        for bit in tms_path(self.monitor.state,'SHIFT_IR' if ir else 'SHIFT_DR'):await self.pulse(bit)
        result=0
        for i in range(bits):result|=(await self.pulse(int(i==bits-1),(value>>i)&1))<<i
        for bit in tms_path(self.monitor.state,'RTI'):await self.pulse(bit)
        return result
