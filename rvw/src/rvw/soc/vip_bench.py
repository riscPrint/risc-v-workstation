"""Generate a separate directed cocotb test for each composed MMIO bus."""
import json
from .model import load
from rvw.uvm.composed import TEST


def generate(directory):
    config = json.loads((directory/'bindings.json').read_text())
    groups = {}
    for region in load(directory/'map.json')['regions']:
        if region['kind'] != 'mmio':
            continue
        names = [region['name']+'.'+reg['name'] for reg in region['registers']
                 if reg['width']==32 and reg['access']!='w' and reg['reset'] is not None]
        if not names:
            raise ValueError('VIP bench needs expected readable registers for ' + region['name'])
        groups[region['name']] = names
    config['bus_tests'] = groups
    (directory/'bindings.json').write_text(json.dumps(config,indent=2)+'\n')
    # Reuse the existing frontdoor implementation. Each test starts from reset
    # and gets its own APB monitor and independent register oracle.
    prefix = TEST.split('@pyuvm.test()')[0]
    (directory/'test_composed.py').write_text(prefix + BODY)
    return groups


BODY = '''
from rvw.vip.apb import Monitor
from rvw.checks.soc_registers import RegisterEffects


def make_test(bus_name, register_names):
    @cocotb.test(name='bus_'+bus_name)
    async def bench(dut):
        here = Path(__file__).resolve().parent
        cfg = json.loads((here/'bindings.json').read_text())
        for field in ('valid','address','write','wdata','mask'):
            getattr(dut,'core_stimulus_'+field).value = 0
        for field,value in cfg['idle_inputs'].items():
            getattr(dut,field).value = value
        oracle = RegisterEffects(here/cfg['map'])
        from rvw.soc.model import load
        region = next(r for r in load(here/cfg['map'])['regions'] if r['name']==bus_name)
        def completed(t):
            assert not t.aborted, 'VIP_ABORTED_TRANSFER'
            oracle.observe(region['base']+t.address,t.write,t.data,t.response,error=t.error)
        monitor = Monitor(completed)
        async def sample():
            while True:
                await RisingEdge(dut.clk)
                value = int(getattr(dut,bus_name+'_probe').value)
                fields = {}
                for field,width in [('pslverr',1),('pready',1),('prdata',32),('pwdata',32),('pwrite',1),('penable',1),('psel',1)]:
                    fields[field] = value & ((1 << width)-1)
                    value >>= width
                fields['paddr'] = value
                monitor.sample(Pins(reset_n=1-int(dut.reset.value),**fields))
        task = cocotb.start_soon(sample())
        await start(dut)
        frontdoor = Frontdoor(dut,cfg['max_cycles'])
        ral = RegisterModel(here/cfg['map'],frontdoor)
        for name in register_names:
            await ral.read(name,check=True)
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
        report = oracle.finish()
        assert not monitor.pending and report['checks']>0, 'VIP_NO_CHECKS'
        task.cancel()
        (here/('checks-'+bus_name+'.json')).write_text(json.dumps(report))
    return bench

HERE = Path(__file__).resolve().parent
for bus_name, registers in json.loads((HERE/'bindings.json').read_text())['bus_tests'].items():
    globals()['test_bus_'+bus_name] = make_test(bus_name,registers)
'''
