"""rvw.chi-like/1: reduced coherent event model. Not an Arm CHI implementation."""
from collections import Counter
from dataclasses import dataclass
from .apb import ProtocolError

SCHEMA='rvw.chi-like/1'


@dataclass(frozen=True)
class Event:
    kind:int=0  # 0=request, 1=snoop acknowledgement, 2=completion
    txn:int=0
    node:int=0
    line:int=0
    op:int=0  # 0=ReadShared, 1=ReadUnique, 2=WriteBack
    data:int=0


class Directory:
    """Independent trace checker. One active transaction per cache line.

    ReadUnique invalidates other holders. ReadShared downgrades an owner.
    WriteBack requires unique ownership and writes the request's data.
    All transactions consume a source credit until completion.
    """
    def __init__(self,nodes=4,credits=4):
        if not 1<=nodes<=16 or credits<1:raise ValueError('coherent nodes or credits')
        self.nodes,self.limit=nodes,credits;self.reset()
    def reset(self):
        self.credit=[self.limit]*self.nodes;self.pending={};self.memory={};self.holders={};self.owner={};self.coverage=Counter()
    def observe(self,e):
        if not 0<=e.node<self.nodes or not 0<=e.txn<16 or e.line<0 or e.line%64 or not 0<=e.data<2**64:
            raise ProtocolError('COH_PROFILE')
        holders=self.holders.setdefault(e.line,set())
        if e.kind==0:
            if e.txn in self.pending:raise ProtocolError('COH_DUPLICATE_TXN')
            if any(request.line==e.line for request,_ in self.pending.values()):raise ProtocolError('COH_LINE_BUSY')
            if not self.credit[e.node]:raise ProtocolError('COH_NO_CREDIT')
            if e.op not in (0,1,2):raise ProtocolError('COH_OPCODE')
            if e.op==2 and self.owner.get(e.line)!=e.node:raise ProtocolError('COH_NOT_OWNER')
            owner=self.owner.get(e.line)
            snoops=(holders-{e.node}) if e.op==1 else ({owner} if e.op==0 and owner is not None and owner!=e.node else set())
            self.pending[e.txn]=(e,set(snoops));self.credit[e.node]-=1
        elif e.kind in (1,2):
            if e.txn not in self.pending:raise ProtocolError('COH_UNKNOWN_TXN')
            request,snoops=self.pending[e.txn]
            if e.line!=request.line:raise ProtocolError('COH_LINE_MISMATCH')
            if e.kind==1:
                if e.node not in snoops:raise ProtocolError('COH_UNEXPECTED_SNOOP_ACK')
                snoops.remove(e.node)
                if request.op==1:holders.discard(e.node)
            else:
                if e.node!=request.node or snoops:raise ProtocolError('COH_INCOMPLETE_SNOOPS')
                expected=request.data if request.op==2 else self.memory.get(e.line,0)
                if e.data!=expected:raise ProtocolError('COH_DATA')
                if request.op==2:
                    self.memory[e.line]=request.data;holders.discard(e.node);self.owner.pop(e.line,None)
                elif request.op==1:
                    if holders-{e.node}:raise ProtocolError('COH_OWNERSHIP')
                    holders.add(e.node);self.owner[e.line]=e.node
                else:holders.add(e.node);self.owner.pop(e.line,None)
                self.credit[e.node]+=1;del self.pending[e.txn]
        else:raise ProtocolError('COH_EVENT_KIND')
        self.coverage[e.kind]+=1
    def finish(self):
        if self.pending:raise ProtocolError('COH_MISSING_COMPLETION')
        if not self.coverage[2]:raise ProtocolError('COH_NO_COMPLETIONS')


class Manager:
    def __init__(self,send):self.send=send
    def request(self,txn,node,line,op=0,data=0):self.send(Event(0,txn,node,line,op,data))
    def acknowledge(self,txn,node,line):self.send(Event(1,txn,node,line))


class Monitor(Directory):pass
class Scoreboard(Directory):pass


def sequences():
    # Acquire, write back, read and transfer unique ownership between nodes.
    return [Event(0,0,0,0,1),Event(2,0,0),Event(0,1,0,0,2,42),Event(2,1,0,data=42),
            Event(0,2,1),Event(2,2,1,data=42),Event(0,3,0,0,1),Event(1,3,1),Event(2,3,0,data=42)]


class CocotbAgent:
    """Project bridge owns translation to its licensed coherent bus."""
    def __init__(self,dut,prefix='coh',hook=lambda e:None):self.dut,self.prefix,self.hook=dut,prefix,hook
    def signal(self,k):return getattr(self.dut,self.prefix+'_'+k)
    async def send(self,e,timeout=100):
        from cocotb.triggers import FallingEdge,RisingEdge
        await FallingEdge(self.dut.clk)
        for k,v in vars(e).items():self.signal(k).value=v
        self.signal('valid').value=1
        for _ in range(timeout):
            await RisingEdge(self.dut.clk)
            if self.signal('ready').value:
                self.hook(e);break
        else:raise TimeoutError('coherent event bridge timeout')
        await FallingEdge(self.dut.clk);self.signal('valid').value=0
