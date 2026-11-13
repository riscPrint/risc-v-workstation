import pytest
from rvw.sim.uvm_models import Transaction, Scoreboard, Memory, RetirementMonitor


def test_scoreboard_all_bins():
    scoreboard=Scoreboard()
    for write in (False,True):
        for address in range(0,16,4):
            t=Transaction(write,address,address+32)
            scoreboard.expect(t); scoreboard.observe(t)
    scoreboard.finish()
    assert scoreboard.checks==8 and len(scoreboard.hit_bins)==8


@pytest.mark.parametrize('fault',['missing','unexpected','mismatch','no_checks'])
def test_scoreboard_faults(fault):
    scoreboard=Scoreboard(); t=Transaction(True,0,10)
    with pytest.raises(AssertionError):
        if fault=='missing': scoreboard.expect(t); scoreboard.finish()
        if fault=='unexpected': scoreboard.observe(t)
        if fault=='mismatch': scoreboard.expect(t); scoreboard.observe(Transaction(True,0,11))
        if fault=='no_checks': scoreboard.finish()


def test_memory_byte_enables_and_bounds():
    memory=Memory(0x80000000,16)
    memory.write(0x80000000,0x44332211,4)
    memory.write(0x80000000,0xaabbccdd,4,mask=5)
    assert memory.read(0x80000000,4)==0x44bb22dd
    for address in (0x7fffffff,0x8000000d):
        with pytest.raises(ValueError): memory.read(address,4)


def test_retirement_reference_required():
    monitor=RetirementMonitor(lambda record: True)
    monitor.observe({'order':0}); monitor.finish()
    with pytest.raises(AssertionError): monitor.observe({'order':0})
    monitor=RetirementMonitor(lambda record: None)
    with pytest.raises(AssertionError): monitor.observe({'order':0})


def test_register_frontdoor_backdoor(tmp_path):
    import asyncio
    import json
    from rvw.sim.uvm_models import RegisterModel
    source=__import__('pathlib').Path(__file__).resolve().parents[2]/'Uvm/tests/registers.json'
    class Bus:
        def __init__(self): self.values={}
        async def read(self,address,width): return self.values.get(address,0)
        async def write(self,address,value,width): self.values[address]=value
    front,back=Bus(),Bus()
    model=RegisterModel(source,front,back)
    name=next(n for n,r in model.registers.items() if r['access']=='rw' and r['write_action']!='one_to_clear')
    async def run():
        await model.write(name,42)
        assert await model.read(name,check=True)==42
        await model.poke(name,13)
        assert await model.peek(name)==13
        with pytest.raises(AssertionError): await model.read(name,check=True)
    asyncio.run(run())


def test_register_side_effects_and_unknown(tmp_path):
    import asyncio,json
    from pathlib import Path
    from rvw.sim.uvm_models import RegisterModel
    source=Path(__file__).resolve().parents[2]/'Uvm/tests/registers.json'
    obj=json.loads(source.read_text())
    regs=obj['regions'][1]['registers']
    regs[0].update(access='r',read_action='clear',reset=7)
    regs[1].update(write_action='one_to_clear',reset=15)
    regs[2].update(reset=None)
    path=tmp_path/'map.json';path.write_text(json.dumps(obj))
    class Bus:
        async def read(self,address,width): return 7
        async def write(self,address,value,width): pass
    model=RegisterModel(path,Bus())
    async def run():
        assert await model.read('csr.word0',check=True)==7
        assert model.mirror['csr.word0']==0
        await model.write('csr.word1',5)
        assert model.mirror['csr.word1']==10
        with pytest.raises(ValueError): await model.write('csr.word0',1)
        with pytest.raises(AssertionError): await model.read('csr.word2',check=True)
        with pytest.raises(ValueError): await model.peek('csr.word0')
    asyncio.run(run())
