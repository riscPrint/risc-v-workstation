"""Optional PCIe transaction-model bridge. No TLP encoding or PHY model."""
from dataclasses import dataclass
from .apb import ProtocolError


@dataclass(frozen=True)
class Window:
    base:int
    size:int
    def __post_init__(self):
        if self.base<0 or self.size<1 or self.size&(self.size-1) or self.base%self.size:raise ValueError('aligned power-of-two PCIe window')
    def contains(self,address,length):return length>0 and self.base<=address and address+length<=self.base+self.size


@dataclass(frozen=True)
class Transaction:
    tag:int
    address:int
    write:bool=False
    data:bytes=b''
    length:int=4


@dataclass(frozen=True)
class Completion:
    tag:int
    data:bytes=b''
    status:str='success'


class Monitor:
    def __init__(self,windows):
        self.windows=list(windows);self.memory={};self.pending={};self.count=0
        for i,w in enumerate(self.windows):
            if any(max(w.base,o.base)<min(w.base+w.size,o.base+o.size) for o in self.windows[:i]):raise ValueError('overlapping PCIe windows')
    def submit(self,t):
        if not 0<=t.tag<256 or t.length<1 or t.length>4096:raise ProtocolError('PCIE_TRANSACTION_PROFILE')
        if not any(w.contains(t.address,t.length) for w in self.windows):raise ProtocolError('PCIE_ADDRESS_WINDOW')
        if t.write:
            if len(t.data)!=t.length:raise ProtocolError('PCIE_WRITE_LENGTH')
            for i,value in enumerate(t.data):self.memory[t.address+i]=value
            self.count+=1
        else:
            if t.tag in self.pending:raise ProtocolError('PCIE_DUPLICATE_TAG')
            self.pending[t.tag]=bytes(self.memory.get(t.address+i,0) for i in range(t.length))
    def complete(self,c):
        if c.tag not in self.pending:raise ProtocolError('PCIE_UNEXPECTED_COMPLETION')
        if c.status!='success' or c.data!=self.pending[c.tag]:raise ProtocolError('PCIE_COMPLETION_DATA')
        del self.pending[c.tag];self.count+=1
    def finish(self):
        if self.pending or not self.count:raise ProtocolError('PCIE_MISSING_COMPLETION')


class Adapter:
    """exchange receives semantic requests, never encoded PCIe packets.

    The project backend must mutate supplied host memory for DMA checks.
    This adapter cannot replace a native model that is not installed.
    """
    def __init__(self,name,version,exchange,windows,dma_windows=()):
        if not name or not version or not callable(exchange):raise ValueError('explicit PCIe backend name, version and bridge required')
        self.name,self.version,self.exchange=name,version,exchange;self.monitor=Monitor(windows);self.dma_windows=list(dma_windows)
        self.memory_enable=self.bus_master=False
    def enumerate(self,vendor,device):
        actual=self.exchange({'kind':'enumerate','backend':self.name,'version':self.version})
        if not isinstance(actual,dict) or (actual.get('vendor'),actual.get('device'))!=(vendor,device):raise ProtocolError('PCIE_ENUMERATION')
        return actual
    def enable(self,memory=True,bus_master=False):
        result=self.exchange({'kind':'command','memory':memory,'bus_master':bus_master})
        if result!={'memory':memory,'bus_master':bus_master}:raise ProtocolError('PCIE_COMMAND_REGISTER')
        self.memory_enable,self.bus_master=memory,bus_master
    def transfer(self,t):
        if not self.memory_enable:raise ProtocolError('PCIE_MEMORY_DISABLED')
        self.monitor.submit(t)
        actual=self.exchange({'kind':'write' if t.write else 'read','tag':t.tag,'address':t.address,'data':t.data,'length':t.length})
        if not t.write:
            if not isinstance(actual,Completion):raise ProtocolError('PCIE_MISSING_COMPLETION')
            self.monitor.complete(actual)
        return actual
    def dma_write(self,address,data,host_memory,host_base=0):
        if not self.bus_master:raise ProtocolError('PCIE_BUS_MASTER_DISABLED')
        if not any(w.contains(address,len(data)) for w in self.dma_windows):raise ProtocolError('PCIE_DMA_WINDOW')
        offset=address-host_base
        if offset<0 or offset+len(data)>len(host_memory):raise ProtocolError('PCIE_HOST_MEMORY_RANGE')
        self.exchange({'kind':'dma_write','address':address,'data':data})
        if bytes(host_memory[offset:offset+len(data)])!=data:raise ProtocolError('PCIE_DMA_EFFECT')
