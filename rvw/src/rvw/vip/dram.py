"""Optional DRAM model contract with bounded independent bank/timing checks."""
from dataclasses import dataclass,asdict
from .apb import ProtocolError

SCHEMA='rvw.vip.dram-model/1'


@dataclass(frozen=True)
class Backend:
    name:str
    version:str
    mode:str
    clock_ps:int
    def __post_init__(self):
        if not self.name or not self.version or self.mode not in ('functional','timing') or self.clock_ps<1:
            raise ValueError('declare DRAM model name, version, mode and clock period')
    def contract(self):return {'schema':SCHEMA,**asdict(self),'scope':'digital commands and data; no board signoff'}


@dataclass(frozen=True)
class Timing:
    rcd:int=2
    rp:int=2
    ras:int=4
    rfc:int=4
    read_latency:int=3
    def __post_init__(self):
        if min(self.rcd,self.rp,self.ras,self.rfc,self.read_latency)<1:raise ValueError('DRAM cycle timing')


@dataclass(frozen=True)
class Command:
    cycle:int
    op:str
    bank:int=0
    row:int=0
    column:int=0
    data:int=0


class Monitor:
    """Explicit reduced ACT/PRE/RD/WR/REF model, full 64-bit writes."""
    def __init__(self,timing=Timing(),banks=8):
        if banks<1:raise ValueError('DRAM bank count')
        self.timing,self.banks=timing,banks;self.reset()
    def reset(self):
        self.open={};self.activated={};self.available=[0]*self.banks;self.memory={};self.last_cycle=-1;self.count=0
    def issue(self,c):
        if c.cycle<=self.last_cycle:raise ProtocolError('DRAM_COMMAND_ORDER')
        if not 0<=c.bank<self.banks or c.row<0 or c.column<0 or not 0<=c.data<2**64:raise ProtocolError('DRAM_PROFILE')
        self.last_cycle=c.cycle;t=self.timing
        if c.cycle<self.available[c.bank]:raise ProtocolError('DRAM_BANK_BUSY')
        if c.op=='ACT':
            if c.bank in self.open:raise ProtocolError('DRAM_ROW_ALREADY_OPEN')
            self.open[c.bank]=c.row;self.activated[c.bank]=c.cycle
        elif c.op=='PRE':
            if c.bank not in self.open or c.cycle-self.activated[c.bank]<t.ras:raise ProtocolError('DRAM_PRECHARGE_TIMING')
            del self.open[c.bank];self.available[c.bank]=c.cycle+t.rp
        elif c.op=='REF':
            if self.open or any(c.cycle<until for until in self.available):raise ProtocolError('DRAM_REFRESH_OPEN_BANK')
            self.available[:]=[c.cycle+t.rfc]*self.banks
        elif c.op in ('RD','WR'):
            if self.open.get(c.bank)!=c.row:raise ProtocolError('DRAM_WRONG_ROW')
            if c.cycle-self.activated[c.bank]<t.rcd:raise ProtocolError('DRAM_RCD')
            key=(c.bank,c.row,c.column)
            if c.op=='WR':self.memory[key]=c.data
            else:self.count+=1;return {'cycle':c.cycle+t.read_latency,'data':self.memory.get(key,0)}
        else:raise ProtocolError('DRAM_UNSUPPORTED_COMMAND')
        return None


class Adapter:
    """execute(command dict, contract dict) must return explicit read evidence.

    The project supplies the native bridge. A missing bridge is an error.
    Mocks validate this contract only and do not qualify a native model.
    """
    def __init__(self,backend,execute,timing=Timing(),banks=8):
        if not callable(execute):raise ValueError('DRAM backend bridge is required')
        self.backend,self.execute=backend,execute;self.monitor=Monitor(timing,banks)
    def issue(self,c):
        expected=self.monitor.issue(c)
        actual=self.execute(asdict(c),self.backend.contract())
        if expected is not None:
            if not isinstance(actual,dict) or actual.get('data')!=expected['data']:raise ProtocolError('DRAM_MODEL_DATA')
            if self.backend.mode=='timing' and actual.get('cycle')!=expected['cycle']:raise ProtocolError('DRAM_MODEL_LATENCY')
        return actual
