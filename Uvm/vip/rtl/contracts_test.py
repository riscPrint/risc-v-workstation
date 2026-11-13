"""Drive seeded RTL semantic endpoints through the existing Python agents."""
from rvw.sim.uvm import require_evidence
import os
import random
import cocotb
from cocotb.clock import Clock
from cocotb.task import bridge, resume
from cocotb.triggers import FallingEdge, RisingEdge, Timer, ClockCycles


@cocotb.test()
async def contracts(d):
    protocol = os.environ['VIP_PROTOCOL']
    code = {'pcie':0, 'ethernet':1, 'dram':2, 'coherent':3}[protocol]
    rng = random.Random(int(os.environ.get('VIP_SEED','17')))
    d.reset_n.value=0; d.valid.value=0; d.buggy.value=int(os.environ['VIP_BAD'])
    d.tag.value=0; d.protocol.value=code; d.command.value=0; d.address.value=0; d.data.value=0
    cocotb.start_soon(Clock(d.clk,10,unit='ns').start())
    await ClockCycles(d.clk,3)
    await FallingEdge(d.clk); d.reset_n.value=1

    observed={}
    @resume
    async def exchange(command, address=0, data=0, tag=0):
        await FallingEdge(d.clk)
        d.command.value=command; d.tag.value=tag; d.address.value=address; d.data.value=data; d.valid.value=1
        await RisingEdge(d.clk); await Timer(1,unit='ns')
        require_evidence(int(d.response_valid.value), 'RTL endpoint response missing')
        result=int(d.response_data.value)
        observed['tag']=int(d.response_tag.value)
        observed['status']=int(d.response_status.value)
        await FallingEdge(d.clk); d.valid.value=0
        return result

    def exercise():
        if protocol=='pcie':
            from rvw.vip.pcie import Adapter, Window, Transaction, Completion
            def backend(request):
                kind=request['kind']
                if kind=='enumerate':
                    value=exchange(0)
                    return dict(vendor=value&65535,device=value>>16)
                if kind=='command':
                    bits=int(request['memory']) | int(request['bus_master'])<<1
                    actual=exchange(1,data=bits)
                    return dict(memory=bool(actual&1),bus_master=bool(actual&2))
                if kind=='write':
                    exchange(2,request['address']//8,int.from_bytes(request['data'],'little'))
                elif kind=='read':
                    data=exchange(3,request['address']//8,tag=request['tag']).to_bytes(8,'little')
                    return Completion(observed['tag'],data)
            agent=Adapter('seeded-rtl','1',backend,[Window(0,2048)])
            agent.enumerate(0x1234,0x5678); agent.enable()
            for index in range(4):
                payload=rng.getrandbits(64).to_bytes(8,'little')
                agent.transfer(Transaction(index,index*8,True,payload,8))
                agent.transfer(Transaction(index,index*8,length=8))
            agent.monitor.finish()
            require_evidence(agent.monitor.count==8, "missing conformance evidence")
        elif protocol=='ethernet':
            from rvw.vip.ethernet import Adapter, Descriptor
            host=bytearray(64)
            def backend(request):
                address=request['address']//8
                if request['kind']=='tx':
                    value=exchange(1,address)
                    return dict(payload=value.to_bytes(8,'little'),error=bool(observed['status']&8),interrupt=bool(observed['status']&1),owned=bool(observed['status']&2))
                length=exchange(2,address,int.from_bytes(request['payload'],'little'))
                # Copy the RTL buffer's observed bytes, not the requested payload.
                host[address*8:address*8+8]=exchange(1,address).to_bytes(8,'little')
                return dict(dropped=bool(observed['status']&4),error=bool(observed['status']&8),length=length,interrupt=bool(observed['status']&1),owned=bool(observed['status']&2))
            agent=Adapter('seeded-rtl','1',backend,host)
            for index in range(4):
                payload=rng.getrandbits(64).to_bytes(8,'little')
                host[index*8:index*8+8]=payload
                exchange(0,index,int.from_bytes(payload,'little'))
                agent.transmit(Descriptor(index*8,8))
                agent.receive(Descriptor(index*8,8),rng.getrandbits(64).to_bytes(8,'little'))
            require_evidence(agent.count==8, "missing conformance evidence")
        elif protocol=='dram':
            from rvw.vip.dram import Adapter, Backend, Command
            def backend(command,contract):
                op={'ACT':0,'PRE':1,'RD':2,'WR':3,'REF':4}[command['op']]
                actual=exchange(op,command['column'],command['data'])
                return dict(data=actual)
            agent=Adapter(Backend('seeded-rtl','1','functional',10000),backend)
            agent.issue(Command(0,'ACT'))
            for index in range(4):
                value=rng.getrandbits(64)
                agent.issue(Command(2+index*2,'WR',column=index,data=value))
                agent.issue(Command(3+index*2,'RD',column=index))
            agent.issue(Command(12,'PRE'))
            require_evidence(agent.monitor.count==4, "missing conformance evidence")
        else:
            from rvw.vip.coherent import Manager, Directory, Event
            scoreboard=Directory(); transaction=0
            def send(request):
                scoreboard.observe(request)
                actual=exchange(request.op,data=request.data)
                scoreboard.observe(Event(2,request.txn,request.node,request.line,data=actual))
            agent=Manager(send)
            for index in range(4):
                node=index%2
                agent.request(transaction,node,0,1);transaction+=1
                agent.request(transaction,node,0,2,rng.getrandbits(64));transaction+=1
            scoreboard.finish()
            require_evidence(scoreboard.coverage[2]==8, "missing conformance evidence")
    await bridge(exercise)()
