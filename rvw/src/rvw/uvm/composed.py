"""Generate a pyuvm RAL bench on a composed SoC's independent test-master wrapper."""
import json
from pathlib import Path
from rvw.soc.configuration import configuration
from rvw.soc.compose import compose
from rvw.soc.model import load, dumps


def generate(source, out, rtl, expected_map=None):
    source, out = Path(source).resolve(), Path(out).resolve()
    spec, _ = configuration(source)
    model = load(source.parent/spec['map'])
    if expected_map is not None and model != load(expected_map):
        raise ValueError('composition map differs from the selected SoC map')
    if spec.get('domains'):
        raise ValueError('independent master bench currently requires one clock domain')
    spec['map'] = str((source.parent/spec['map']).resolve())
    spec.pop('fragments', None)
    spec['core'] = dict(bus='simple', **{'class':'rvwsoc.VerificationCore'}, exports=['stimulus'])
    out.mkdir(parents=True,exist_ok=False)
    (out/'compose.json').write_text(dumps(spec))
    compose(out/'compose.json',out/'composition')
    scala = out/'composition/ComposedSoc.scala'
    text = scala.read_text().replace('package generated','package verification').replace('ComposedSoc','VerificationSoc').replace('object Generate','object VerificationGenerate')
    probes = []
    for region in model['regions']:
        if region['kind'] != 'mmio':
            continue
        name = region['name']
        fields = ['PADDR','PSEL','PENABLE','PWRITE','PWDATA','PRDATA','PREADY','PSLVERROR']
        packed = ' ## '.join(f'{name}.io.bus.{field}.asBits' for field in fields)
        width = region['size'].bit_length()-1+69
        probes += [f'  val {name}_probe = out(Bits({width} bits))', f'  {name}_probe := {packed}']
    text = text.replace('\n}\nobject VerificationGenerate', '\n'+'\n'.join(probes)+'\n}\nobject VerificationGenerate')
    scala.write_text(text)
    registers = [r['name']+'.'+reg['name'] for r in model['regions'] for reg in r['registers']
                 if reg['width'] in (8,16,32) and reg['access'] != 'w' and reg['reset'] is not None]
    if not registers:
        raise ValueError('composed RAL bench needs readable registers with known resets')
    # Exported peripheral inputs need explicit idle values. UART RX and PLIC
    # sources are board data, so callers supply them in bench bindings.
    (out/'map.json').write_text(dumps(model))
    config = dict(map='map.json',registers=registers,idle_inputs={},max_cycles=1000)
    (out/'bindings.json').write_text(dumps(config))
    (out/'test_composed.py').write_text(TEST)
    manifest = dict(schema='rvw.cocotb/1',name='composed_ral',backend='verilator',top='VerificationSoc',
        sources=[str(Path(rtl).resolve())],test_module='test_composed',python_paths=['.'],requires=['timer'],
        clock=dict(signal='clk',period_ns=10),reset=dict(signal='reset',active=1,cycles=5))
    (out/'bench.json').write_text(dumps(manifest))
    return dict(status='generated',manifest=str(out/'bench.json'),scala=str(scala),checks=len(registers),
                scope='same composed peripheral fabric with an independent master; CPU execution is excluded')


TEST = '''import json
from pathlib import Path
import cocotb
import pyuvm
from cocotb.triggers import FallingEdge, RisingEdge
from rvw.sim.bench import start
from rvw.sim.uvm_models import RegisterModel
from rvw.uvm.soc import SocRegisterEnvironment
from rvw.vip.apb import Pins

class Frontdoor:
    def __init__(self, dut, max_cycles):
        self.dut, self.max_cycles = dut, max_cycles
        self.transfers = 0
    async def transfer(self, address, write=False, data=0):
        d = self.dut
        await FallingEdge(d.clk)
        d.core_stimulus_address.value = address
        d.core_stimulus_write.value = int(write)
        d.core_stimulus_wdata.value = data
        d.core_stimulus_mask.value = 15 if write else 0
        d.core_stimulus_valid.value = 1
        for _ in range(self.max_cycles):
            await RisingEdge(d.clk)
            if int(d.core_stimulus_ready.value):
                assert not int(d.core_stimulus_error.value), 'SOC_FRONTDOOR_ERROR'
                value = int(d.core_stimulus_rdata.value)
                await FallingEdge(d.clk)
                d.core_stimulus_valid.value = 0
                self.transfers += 1
                return value
        raise AssertionError('SOC_FRONTDOOR_TIMEOUT')
    async def read(self, address, width):
        assert width in (8,16,32)
        return (await self.transfer(address)) & ((1 << width)-1)
    async def write(self, address, data, width):
        assert width in (8,16,32)
        await self.transfer(address, True, data & ((1 << width)-1))

@pyuvm.test()
class ComposedRegisters(pyuvm.uvm_test):
    async def run_phase(self):
        self.raise_objection()
        try:
            here = Path(__file__).resolve().parent
            cfg = json.loads((here/'bindings.json').read_text())
            dut = cocotb.top
            for field in ('valid','address','write','wdata','mask'):
                getattr(dut,'core_stimulus_'+field).value = 0
            for field,value in cfg['idle_inputs'].items():
                getattr(dut,field).value = value
            environment = SocRegisterEnvironment(here/cfg['map'])
            async def monitor():
                while True:
                    await RisingEdge(dut.clk)
                    reset_n = 1-int(dut.reset.value)
                    if not reset_n:
                        environment.reset()
                    for name,bus in environment.buses.items():
                        value = int(getattr(dut,name+'_probe').value)
                        fields = {}
                        for field,width in [('pslverr',1),('pready',1),('prdata',32),('pwdata',32),('pwrite',1),('penable',1),('psel',1)]:
                            fields[field] = value & ((1 << width)-1)
                            value >>= width
                        fields['paddr'] = value
                        bus.sample(Pins(reset_n=reset_n,**fields))
            task = cocotb.start_soon(monitor())
            await start(dut)
            frontdoor = Frontdoor(dut,cfg['max_cycles'])
            ral = RegisterModel(here/cfg['map'],frontdoor)
            for name in cfg['registers']:
                await ral.read(name,check=True)
                reg = ral.registers[name]
                if reg['read_action'] == 'clear':
                    await ral.read(name,check=True)
                if reg['write_action'] == 'one_to_clear' and reg['access'] == 'rw':
                    await ral.write(name,(1 << reg['width'])-1)
                    await ral.read(name,check=True)
            assert frontdoor.transfers > 0, 'SOC_NO_REGISTER_CHECKS'
            await RisingEdge(dut.clk)
            await FallingEdge(dut.clk)
            report = environment.finish()
            assert report['checks'] > 0 and not report['unexercised'], 'SOC_UNEXERCISED_BUS'
            task.cancel()
            (here/'checks.json').write_text(json.dumps(dict(checks=report['checks'],transfers=frontdoor.transfers,registers=cfg['registers'],environment=report)))
        finally:
            self.drop_objection()
'''
