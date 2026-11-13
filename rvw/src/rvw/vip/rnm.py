"""Real-number boundary stub contract only. No analog behavior or solver."""
from dataclasses import dataclass,asdict
import math
from .apb import ProtocolError

SCHEMA='rvw.vip.rnm-stub/1'


@dataclass(frozen=True)
class Channel:
    name:str
    unit:str
    def __post_init__(self):
        if not self.name or not self.unit:raise ValueError('RNM channel name and unit are required')


@dataclass(frozen=True)
class Sample:
    time_fs:int
    value:float
    valid:bool=True
    known:bool=True


class BoundaryStub:
    def __init__(self,backend,version,channels,supports_real=False):
        if not backend or not version:raise ValueError('RNM backend and version are required')
        if supports_real is not True:raise ValueError('backend must explicitly support real-number handles')
        self.backend,self.version=backend,version;self.channels={c.name:c for c in channels};self.latest={}
        if not self.channels:raise ValueError('declare at least one RNM channel')
    def contract(self):
        return {'schema':SCHEMA,'backend':self.backend,'version':self.version,'supports_real':True,
                'time_unit':'fs','channels':[asdict(c) for c in self.channels.values()],
                'scope':'interface stub only; no analog model is bound'}
    def observe(self,name,sample):
        if name not in self.channels:raise ProtocolError('RNM_UNKNOWN_CHANNEL')
        if not sample.valid:return None
        if not sample.known or not math.isfinite(sample.value):raise ProtocolError('RNM_UNKNOWN_VALUE')
        if sample.time_fs<0 or (name in self.latest and sample.time_fs<self.latest[name].time_fs):raise ProtocolError('RNM_TIME_ORDER')
        self.latest[name]=sample;return sample
    def evaluate(self):
        return {'status':'inconclusive','cause':'model_not_bound','contract':self.contract(),
                'observed_channels':sorted(self.latest)}


class CocotbBoundary(BoundaryStub):
    """Project supplies real-value, known and valid handles explicitly."""
    async def sample(self,name,value_handle,known_handle,valid_handle,time_fs):
        from cocotb.triggers import ReadOnly
        await ReadOnly()
        try:sample=Sample(time_fs,float(value_handle.value),bool(int(valid_handle.value)),bool(int(known_handle.value)))
        except (ValueError,TypeError) as exc:raise ProtocolError('RNM_UNKNOWN_VALUE') from exc
        return self.observe(name,sample)
