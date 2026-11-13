"""Optional Ethernet MAC client-packet bridge. No PHY or FCS encoding."""
from collections import deque
from dataclasses import dataclass
from .apb import ProtocolError


@dataclass(frozen=True)
class Descriptor:
    address:int
    length:int
    owned:bool=True


class Scoreboard:
    def __init__(self):self.expected=deque();self.count=0
    def expect(self,payload):self.expected.append(bytes(payload))
    def observe(self,payload):
        if not self.expected or self.expected.popleft()!=bytes(payload):raise ProtocolError('ETH_PACKET_DATA')
        self.count+=1
    def finish(self):
        if self.expected or not self.count:raise ProtocolError('ETH_MISSING_PACKET')


class Adapter:
    """Project exchange callback supplies native packet-model observations.

    A receive callback must mutate the shared host memory. Returned metadata
    alone does not prove DMA effects. Drops must leave the descriptor region
    unchanged. Descriptor ownership is returned to software on completion.
    """
    def __init__(self,name,version,exchange,host_memory,host_base=0,max_packet=9216):
        if not name or not version or not callable(exchange):raise ValueError('explicit Ethernet model name, version and bridge required')
        self.name,self.version,self.exchange=name,version,exchange
        self.memory,self.base,self.max_packet=host_memory,host_base,max_packet
        self.count=0
    def region(self,d):
        offset=d.address-self.base
        if not d.owned:raise ProtocolError('ETH_DESCRIPTOR_OWNERSHIP')
        if d.length<1 or offset<0 or offset+d.length>len(self.memory):raise ProtocolError('ETH_DMA_RANGE')
        return offset
    def transmit(self,d):
        offset=self.region(d)
        if d.length>self.max_packet:raise ProtocolError('ETH_PACKET_LENGTH')
        expected=bytes(self.memory[offset:offset+d.length])
        actual=self.exchange({'kind':'tx','address':d.address,'length':d.length})
        if not isinstance(actual,dict) or actual.get('payload')!=expected or actual.get('error'):
            raise ProtocolError('ETH_TX_DATA_OR_ERROR')
        if not actual.get('interrupt') or actual.get('owned',True):raise ProtocolError('ETH_DESCRIPTOR_COMPLETION')
        self.count+=1;return actual
    def receive(self,d,payload,drop=False,error=False):
        offset=self.region(d);payload=bytes(payload)
        if not 1<=len(payload)<=min(d.length,self.max_packet):raise ProtocolError('ETH_PACKET_LENGTH')
        before=bytes(self.memory[offset:offset+d.length])
        actual=self.exchange({'kind':'rx','address':d.address,'capacity':d.length,'payload':payload})
        if not isinstance(actual,dict) or actual.get('dropped')!=drop or actual.get('error')!=error:raise ProtocolError('ETH_RX_OUTCOME')
        if drop or error:
            if bytes(self.memory[offset:offset+d.length])!=before:raise ProtocolError('ETH_DROP_DMA_EFFECT')
            if actual.get('interrupt') or actual.get('owned') is not True:raise ProtocolError('ETH_DROP_DESCRIPTOR')
        else:
            expected=payload+before[len(payload):]
            if bytes(self.memory[offset:offset+d.length])!=expected:raise ProtocolError('ETH_RX_DMA_EFFECT')
            if actual.get('length')!=len(payload) or not actual.get('interrupt') or actual.get('owned',True):
                raise ProtocolError('ETH_DESCRIPTOR_COMPLETION')
        self.count+=1;return actual
