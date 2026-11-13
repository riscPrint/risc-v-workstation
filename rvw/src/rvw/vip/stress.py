"""Abstract memory-controller/NoC traffic. No DDR electrical or NoC wire claim."""
from collections import Counter
from dataclasses import dataclass
import random
from .apb import ProtocolError, NoChecks


@dataclass(frozen=True)
class Request:
    txn:int
    source:int=0
    address:int=0
    write:bool=False
    data:int=0
    qos:int=0


@dataclass(frozen=True)
class Response:
    txn:int
    source:int=0
    data:int=0
    error:bool=False


@dataclass(frozen=True)
class Config:
    nodes:int=4
    credits:int=4
    depth:int=64
    latency:int=2
    jitter:int=4
    bandwidth:int=2
    refresh_period:int=16
    refresh_cycles:int=3
    max_wait:int=32
    def __post_init__(self):
        if min(self.nodes,self.credits,self.depth,self.latency,self.bandwidth,self.refresh_period,self.max_wait)<1:
            raise ValueError('stress configuration')
        if self.jitter<0 or not 0<=self.refresh_cycles<self.refresh_period:raise ValueError('stress pauses')


class Monitor:
    def __init__(self,config=Config()):
        self.config=config;self.pending={};self.used=Counter();self.memory={};self.coverage=Counter();self.cycle=-1
    def advance(self,cycle):
        if cycle<self.cycle:raise ProtocolError('STRESS_TIME_ORDER')
        self.cycle=cycle
        if any(cycle-start>self.config.max_wait for _,start,_ in self.pending.values()):raise ProtocolError('STRESS_STARVATION')
    def request(self,r,cycle):
        self.advance(cycle);key=(r.source,r.txn);c=self.config
        if not 0<=r.source<c.nodes or r.txn<0 or r.qos not in (0,1,2,3):raise ProtocolError('STRESS_PROFILE')
        if key in self.pending:raise ProtocolError('STRESS_DUPLICATE_TXN')
        if self.used[r.source]>=c.credits:raise ProtocolError('STRESS_NO_CREDIT')
        error=not 0<=r.address<c.depth
        expected=Response(r.txn,r.source,0 if error or r.write else self.memory.get(r.address,0),error)
        if r.write and not error:self.memory[r.address]=r.data
        self.pending[key]=(r,cycle,expected);self.used[r.source]+=1;self.coverage[('qos',r.qos)]+=1
    def response(self,r,cycle):
        self.advance(cycle);key=(r.source,r.txn)
        if key not in self.pending:raise ProtocolError('STRESS_UNKNOWN_RESPONSE')
        request,start,expected=self.pending[key]
        if cycle-start<self.config.latency:raise ProtocolError('STRESS_EARLY_RESPONSE')
        if r!=expected:raise ProtocolError('STRESS_RESPONSE_DATA')
        self.used[r.source]-=1;del self.pending[key];self.coverage['responses']+=1
        self.coverage['latency_sum']+=cycle-start;self.coverage['errors']+=int(r.error)
    def finish(self):
        if self.pending:raise ProtocolError('STRESS_MISSING_RESPONSE')
        if not self.coverage['responses']:raise NoChecks('STRESS_NO_RESPONSES')


class Subordinate:
    """Seeded abstract service model with QoS priority and bounded bandwidth."""
    def __init__(self,seed=1,config=Config(),buggy=False):
        self.rng=random.Random(seed);self.config=config;self.buggy=buggy;self.queue=[];self.memory={};self.last_cycle=-1
    def step(self,cycle,requests=()):
        if cycle<=self.last_cycle:raise ValueError('one service step per increasing cycle')
        self.last_cycle=cycle;c=self.config
        for r in requests:
            error=not 0<=r.address<c.depth
            data=0 if error or r.write else self.memory.get(r.address,0)
            if r.write and not error:self.memory[r.address]=r.data
            response=Response(r.txn,r.source,data^int(self.buggy),error)
            self.queue.append((cycle+c.latency+self.rng.randrange(c.jitter+1),-r.qos,response))
        if cycle%c.refresh_period<c.refresh_cycles:return []
        ready=sorted((entry for entry in self.queue if entry[0]<=cycle),key=lambda e:(e[1],e[0]))[:c.bandwidth]
        for entry in ready:self.queue.remove(entry)
        return [entry[2] for entry in ready]


class Manager:
    def __init__(self,service,config=Config()):self.service=service;self.config=config;self.monitor=Monitor(config)
    def run(self,requests,limit=1000):
        queued=list(requests);index=0
        for cycle in range(limit):
            accepted=[]
            if index<len(queued):
                r=queued[index]
                if self.monitor.used[r.source]<self.config.credits:
                    self.monitor.request(r,cycle);accepted=[r];index+=1
            for response in self.service.step(cycle,accepted):self.monitor.response(response,cycle)
            self.monitor.advance(cycle)
            if index==len(queued) and not self.monitor.pending:self.monitor.finish();return dict(self.monitor.coverage)
        raise TimeoutError('stress campaign cycle limit')


def sequences(seed=1,count=32,config=Config()):
    rng=random.Random(seed)
    for i in range(count):
        yield Request(i, i%config.nodes,rng.randrange(config.depth+1),bool(i%2),rng.getrandbits(64),i%4)


class Scoreboard(Monitor):pass


class CocotbAgent:
    """Send abstract events. A project owns bus translation and cycle stamps."""
    def __init__(self,dut,prefix='stress'):self.dut,self.prefix=dut,prefix
    def signal(self,k):return getattr(self.dut,self.prefix+'_'+k)
    async def send(self,event,timeout=100):
        from cocotb.triggers import FallingEdge,RisingEdge
        response=isinstance(event,Response)
        values=dict(response=int(response),txn=event.txn,source=event.source,
                    address=getattr(event,'address',0),write=int(getattr(event,'write',False)),
                    data=event.data,error=int(getattr(event,'error',False)),qos=getattr(event,'qos',0))
        await FallingEdge(self.dut.clk)
        for k,v in values.items():self.signal(k).value=v
        self.signal('valid').value=1
        for _ in range(timeout):
            await RisingEdge(self.dut.clk)
            if int(self.signal('ready').value):break
        else:raise TimeoutError('stress event bridge timeout')
        await FallingEdge(self.dut.clk);self.signal('valid').value=0
