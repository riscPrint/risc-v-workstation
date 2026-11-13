"""Native AXI/TileLink matrices and wide lane checks with independent VIP."""
import json
import random
from pathlib import Path
from types import SimpleNamespace
import cocotb
from cocotb.triggers import RisingEdge,ClockCycles,FallingEdge
from rvw.sim.bench import start
from rvw.vip import axi,tilelink


class Constant:
    def __init__(self,value):self.constant=value
    @property
    def value(self):return self.constant
    @value.setter
    def value(self,value):
        assert int(value)==self.constant,'PROJECT_CONSTANT_PIN'


class Reset:
    def __init__(self,d):self.d=d
    @property
    def value(self):return 1-int(self.d.reset.value)


def axi_view(d,rtl,prefix):
    pins=dict(clk=d.clk,reset_n=Reset(d))
    shape=axi.CocotbAgent(None,'shape')
    for channel in ('aw','w','b','ar','r'):
        for suffix in ('valid','ready'):
            pins[prefix+'_'+channel+suffix]=getattr(d,rtl+'_'+channel+'_'+suffix)
        for field,name in shape.fields(channel):
            path=rtl+'_'+channel+'_payload_'+name
            handle=getattr(d,path,None)
            if handle is None:
                assert name in ('lock','prot','cache','id','burst'),path
                handle=Constant(1 if name=='burst' else 0)
            pins[prefix+'_'+channel+name]=handle
    return SimpleNamespace(**pins)


def tl_view(d,rtl,prefix):
    pins=dict(clk=d.clk,reset_n=Reset(d))
    for channel,cls in [('a',tilelink.Request),('d',tilelink.Response)]:
        for suffix in ('valid','ready'):
            pins[prefix+'_'+channel+'_'+suffix]=getattr(d,rtl+'_'+channel+'_'+suffix)
        for field in cls.__dataclass_fields__:
            path=rtl+'_'+channel+'_payload_'+field
            handle=getattr(d,path,None)
            if handle is None:
                assert field in ('sink','param','corrupt'),path
                handle=Constant(0)
            pins[prefix+'_'+channel+'_'+field]=handle
    return SimpleNamespace(**pins)


async def axi_target(agent,errors=None):
    model=axi.Subordinate(31,data_bytes=agent.data_bytes,errors=errors)
    while True:
        await FallingEdge(agent.dut.clk)
        pending=model.step(agent.pins(),commit=False)
        agent.drive(pending,True)
        await RisingEdge(agent.dut.clk)
        model.step(agent.pins(),driven=pending)


@cocotb.test()
async def matrix(d):
    if d._name=='NativeTlFabricFixture':
        await tl_matrix(d)
    else:
        await axi_matrix(d)


async def axi_matrix(d):
    crossbar=d._name=='NativeAxiFabricFixture'
    incoming=4 if crossbar else len(d.io_up_w_payload_data)//8
    outgoing=4 if crossbar else len(d.io_down_w_payload_data)//8
    count=2 if crossbar else 1
    clients=[];targets=[];tasks=[];client_boards=[];target_boards=[]
    for i in range(count):
        prefix='m'+str(i);rtl='io_inputs_'+str(i) if crossbar else 'io_up'
        board=axi.Scoreboard(incoming);client_boards.append(board)
        client=axi.CocotbAgent(axi_view(d,rtl,prefix),prefix,board.observe,data_bytes=incoming)
        client.drive(axi.Pins());clients.append(client)
    for j in range(count):
        prefix='s'+str(j);rtl='io_outputs_'+str(j) if crossbar else 'io_down'
        board=axi.Scoreboard(outgoing);target_boards.append(board)
        target=axi.CocotbAgent(axi_view(d,rtl,prefix),prefix,board.observe,data_bytes=outgoing)
        target.drive(axi.Pins(),True);targets.append(target)
        errors=None if crossbar else {('read',0x300):2,('write',0x320):2}
        tasks.append(cocotb.start_soon(axi_target(target,errors)))
    for agent in clients+targets:tasks.append(cocotb.start_soon(agent.run_monitor()))
    simultaneous=0
    async def observe_parallel():
        nonlocal simultaneous
        while True:
            await RisingEdge(d.clk)
            fired=sum(int(a.pins().arvalid and a.pins().arready) for a in targets)
            if fired>1:simultaneous+=1
    if crossbar:tasks.append(cocotb.start_soon(observe_parallel()))
    await start(d)
    async def traffic(i,agent):
        rng=random.Random(31+i)
        for k in range(16):
            bank=(k+i)%2 if crossbar else 0
            base=(0x1000 if bank==0 else 0x2000) if crossbar else 0
            address=base+0x100+i*0x200+(k%4)*0x40
            size=incoming.bit_length()-1
            length=(0,1,3,7)[k%4]
            burst=(1,0,2,1)[k%4]
            if burst==2:address+=2*incoming
            a=axi.Address(address,id=k%2,length=length,size=size,burst=burst)
            beats=[axi.Write(rng.getrandbits(8*incoming),(1<<incoming)-1,n==length) for n in range(length+1)]
            result=await agent.transfer(a,beats,response_stall=20)
            assert len(result)==1 and result[0].id==a.id and result[0].response==0,'AXI_WRITE_RESPONSE'
            result=await agent.transfer(a,response_stall=20)
            assert len(result)==length+1 and all(b.id==a.id and b.response==0 for b in result),'AXI_READ_RESPONSE'
        # Change one high byte without changing its neighboring lanes.
        base=0x1000 if crossbar else 0
        a=axi.Address(base+0x100+i*0x200+incoming-1,id=1,size=0)
        beat=axi.Write(0xa5<<(8*(incoming-1)),1<<(incoming-1))
        assert (await agent.transfer(a,[beat],response_stall=20))[0].response==0
        await agent.transfer(axi.Address(base+0x100+i*0x200,id=1,size=incoming.bit_length()-1),response_stall=20)
    jobs=[cocotb.start_soon(traffic(i,a)) for i,a in enumerate(clients)]
    for job in jobs:await job
    # Compare endpoint bytes with original client writes. Inverse lane bugs in
    # both conversion directions must not cancel in an end-to-end readback.
    for board in client_boards:
        for address,value in board.memory.items():
            target=0 if not crossbar or address<0x2000 else 1
            assert target_boards[target].memory.get(address,0)==value,'AXI_ENDPOINT_BYTES'
    errors_checked=0
    if not crossbar:
        a=axi.Address(0x300,id=1,size=incoming.bit_length()-1)
        result=await clients[0].transfer(a,response_stall=20)
        assert any(r.response>=2 for r in result),'EARLY_NARROW_READ_ERROR_LOST'
        a=axi.Address(0x320,id=1,size=incoming.bit_length()-1)
        result=await clients[0].transfer(a,[axi.Write(0x12345678,(1<<incoming)-1)],response_stall=20)
        assert result[0].response>=2,'EARLY_NARROW_WRITE_ERROR_LOST'
        errors_checked=2
    await ClockCycles(d.clk,5)
    for agent in clients+targets:agent.monitor.finish()
    stalls=sum(a.monitor.coverage[('stall','b')]+a.monitor.coverage[('stall','r')] for a in clients)
    assert stalls>0,'RESPONSE_BACKPRESSURE_NOT_EXERCISED'
    if crossbar:assert simultaneous>0,'PARALLEL_BANKS_NOT_EXERCISED'
    for task in tasks:task.cancel()
    Path('fabric-checks.json').write_text(json.dumps(dict(kind=d._name,client_checks=[b.count for b in client_boards],
        endpoint_checks=[b.count for b in target_boards],response_stalls=stalls,parallel_cycles=simultaneous,errors_checked=errors_checked)))


async def tl_matrix(d):
    clients=[];targets=[];boards=[];target_boards=[];tasks=[]
    for i in range(2):
        prefix='m'+str(i);board=tilelink.Scoreboard();boards.append(board)
        def observe(event,board=board):
            if event[0][0].address!=0x90000000:board.observe(event)
        client=tilelink.CocotbAgent(tl_view(d,'io_inputs_'+str(i),prefix),prefix,observe,uh=True)
        client.drive(tilelink.Pins());clients.append(client)
    for i in range(2):
        prefix='s'+str(i);board=tilelink.Scoreboard();target_boards.append(board)
        target=tilelink.CocotbAgent(tl_view(d,'io_outputs_'+str(i),prefix),prefix,board.observe,uh=True)
        target.drive(tilelink.Pins(),True);targets.append(target)
        tasks.append(cocotb.start_soon(target.run_subordinate(seed=31+i)))
    for a in clients+targets:tasks.append(cocotb.start_soon(a.run_monitor()))
    simultaneous=0
    async def parallel():
        nonlocal simultaneous
        while True:
            await RisingEdge(d.clk)
            if sum(int(a.pins().a_valid and a.pins().a_ready) for a in targets)>1:simultaneous+=1
    tasks.append(cocotb.start_soon(parallel()))
    await start(d)
    async def traffic(i,agent):
        for k in range(12):
            bank=(k+i)%2
            address=(0x1000 if bank==0 else 0x2000)+i*0x200+(k%4)*64
            size=(2,3,4,6)[k%4]
            count=max(1,(1<<size)//4)
            data=[(0x12340000 | i<<12 | k<<4 | n) for n in range(count)]
            requests=[tilelink.Request(opcode=0,size=size,source=k%4,address=address,data=value) for value in data]
            result=await agent.transfer(requests)
            assert len(result)==1 and not result[0].denied,'TL_WRITE_RESPONSE'
            result=await agent.transfer([tilelink.Request(size=size,source=k%4,address=address)])
            assert [r.data for r in result]==data and not any(r.denied for r in result),'TL_READ_DATA'
    jobs=[cocotb.start_soon(traffic(i,a)) for i,a in enumerate(clients)]
    for job in jobs:await job
    for board in boards:
        for address,value in board.model.bytes.items():
            target=0 if address<0x2000 else 1
            base=0x1000 if target==0 else 0x2000
            assert target_boards[target].model.bytes.get(address-base,0)==value,'TL_ENDPOINT_BYTES'
    result=await clients[0].transfer([tilelink.Request(address=0x90000000)])
    assert result[0].denied and result[0].corrupt,'TL_UNMAPPED_DENIED'
    await ClockCycles(d.clk,5)
    for agent in clients+targets:agent.monitor.finish()
    assert simultaneous>0,'TL_PARALLEL_BANKS_NOT_EXERCISED'
    for task in tasks:task.cancel()
    Path('fabric-checks.json').write_text(json.dumps(dict(kind=d._name,client_checks=[b.count for b in boards],
        endpoint_checks=[b.count for b in target_boards],parallel_cycles=simultaneous,unmapped_denied=True)))
