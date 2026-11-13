"""Generate a runnable pyuvm APB register-reset bench from SpinalDB and SoC data."""
import json
from pathlib import Path
from rvw.query.db import DesignDB
from rvw.soc.model import load

BUS_TYPES = {'Apb3':'apb', 'Apb4':'apb', 'Axi4':'axi', 'AxiLite4':'axi-lite',
             'Axi4Stream':'axis', 'AhbLite3':'ahb', 'Tilelink':'tilelink', 'Uart':'uart'}


def bus_type(class_name):
    leaf = (class_name or '').split('.')[-1].split('$')[0]
    return BUS_TYPES.get(leaf)


def generate(db=None, soc=None, out=None, *, rtl=None, language='pyuvm', profile='auto', adapter=None, composition=None, port_map=None):
    if port_map is not None:
        if adapter is not None or composition is not None:
            raise ValueError("port_map cannot be combined with adapter or composition")
        from .declared import generate as declared
        return declared(db,soc,out,rtl=rtl,language=language,profile=profile,port_map=port_map)
    if composition is not None:
        if db is not None or adapter is not None or language != 'pyuvm':
            raise ValueError('composition profile needs pyuvm without database or adapter')
        from .composed import generate as composed
        if rtl and len(rtl) != 1:
            raise ValueError('composition profile requires one generated RTL file')
        return composed(composition, out, list(rtl)[0] if rtl else Path(out)/'rtl/VerificationSoc.v', expected_map=soc)
    if db is None or soc is None:
        raise ValueError('database-selected profiles require db and soc')
    if adapter is not None:
        from .profiles import generate as generate_profile
        return generate_profile(db, soc, out, rtl=rtl, language=language, profile=profile, adapter=adapter)
    from .profiles import classify
    with_db = DesignDB(Path(db).resolve())
    try:
        classes = [c for c, in with_db.conn.execute(
            'SELECT b.class_name FROM bundles b JOIN components c ON b.component_id=c.id WHERE c.parent_id IS NULL')]
        discovered = [classify(c) for c in classes if classify(c)]
    finally:
        with_db.close()
    if not discovered:
        if any(bus_type(c) for c in classes):
            raise ValueError('automatic runnable profile requires one top-level APB bus')
        load(soc)
        return {'status': 'unsupported', 'reason': 'No supported typed bus metadata. Plain HDL ports need a project-owned UVM bench and explicit VIP pin bindings.'}
    if language != 'pyuvm' or profile != 'auto' or (discovered and discovered != ['apb']):
        from .profiles import generate as generate_profile
        return generate_profile(db,soc,out,rtl=rtl,language=language,profile=profile)
    db, soc, out = Path(db).resolve(), Path(soc).resolve(), Path(out).resolve()
    model = load(soc)
    regions = [r for r in model['regions'] if r['kind']=='mmio']
    if len(regions)!=1:
        raise ValueError('scaffold profile requires one MMIO region; multi-bus wiring needs a project adapter')
    readable = [r for r in regions[0]['registers'] if r['access']!='w' and r['reset'] is not None and r['width']==32]
    if not readable:
        raise ValueError('scaffold requires a readable 32-bit register with a declared reset')
    design = DesignDB(db)
    try:
        tops = list(design.conn.execute('SELECT id,module FROM components WHERE parent_id IS NULL'))
        if len(tops)!=1: raise ValueError('design requires one top component')
        component, top = tops[0]
        buses = [dict(path=p,spinal_type=c,agent=bus_type(c)) for p,c in
                 design.conn.execute('SELECT path,class_name FROM bundles WHERE component_id=?',(component,))
                 if bus_type(c)]
        if len(buses)!=1 or buses[0]['agent']!='apb':
            raise ValueError('automatic runnable profile requires one top-level APB bus; found '+json.dumps(buses))
        ports = [name for name, in design.conn.execute('SELECT name FROM signals WHERE component_id=? AND direction IS NOT NULL',(component,))]
        pins = {}
        for field in ('psel','penable','paddr','pwrite','pwdata','pready','prdata','pslverr','pstrb','pprot'):
            matches = [p for p in ports if p.lower()==field or p.lower().endswith('_'+field)]
            if not matches and field in ('pstrb','pprot'): continue
            if len(matches)!=1: raise ValueError('ambiguous or missing APB pin: '+field)
            pins[field]=matches[0]
        domains = list(design.conn.execute('SELECT DISTINCT clock,reset,reset_active_high FROM clock_domains WHERE clock IS NOT NULL AND reset IS NOT NULL'))
        if len(domains)!=1: raise ValueError('scaffold requires one clock and reset domain')
        clock,reset,active = domains[0]
        def port(path):
            matches=[p for p in ports if p==path or p==path.split('.')[-1]]
            if len(matches)!=1: raise ValueError('clock/reset port not found: '+path)
            return matches[0]
        clock,reset=port(clock),port(reset)
        sources = list(rtl) if rtl else [p for p, in design.conn.execute('SELECT path FROM rtl_files')]
    finally:
        design.close()
    sources = [str((db.parent/Path(p)).resolve(strict=True)) for p in sources]
    if not sources: raise ValueError('no RTL files; supply --rtl')
    config = dict(top=top,pins=pins,clock=clock,reset=reset,reset_active=int(active),
                  map='map.json',registers=[regions[0]['name']+'.'+r['name'] for r in readable],agents=buses)
    out.mkdir(parents=True,exist_ok=False)
    (out/'map.json').write_text(soc.read_text())
    (out/'bindings.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'test_generated.py').write_text(TEST)
    manifest = dict(schema='rvw.cocotb/1',name='generated_apb',backend='verilator',top=top,
        sources=sources,test_module='test_generated',python_paths=['.'],requires=['timer'],
        clock=dict(signal=clock,period_ns=10),reset=dict(signal=reset,active=int(active),cycles=5))
    (out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'README.md').write_text('Generated APB pyuvm register-reset bench.\n\n'
        'Run `rvw regress cocotb '+str(out/'bench.json')+' --out /tmp/apb-new`.\n'
        'The test reads declared register resets through the merged APB agent.\n'
        'No CPU, IRQ, debug, multi-bus or C4 acceptance is claimed.\n')
    return dict(out=str(out),manifest=str(out/'bench.json'),agents=buses,checks=len(readable),profile='apb-register-reset')


TEST = '''import json
from pathlib import Path
from types import SimpleNamespace
import cocotb
import pyuvm
from rvw.sim.bench import start
from rvw.sim.uvm_models import RegisterModel
from rvw.vip.apb import CocotbAgent, Transfer

class Constant:
    def __init__(self, value): self.value = value

class Reset:
    def __init__(self, signal, active): self.signal, self.active = signal, active
    @property
    def value(self): return int(int(self.signal.value) != self.active)

class Frontdoor:
    def __init__(self, agent): self.agent = agent
    async def read(self, address, width):
        assert width == 32
        response = await self.agent.transfer(Transfer(address))
        assert not response.error and not response.aborted, 'APB reset read failed'
        return response.response

@pyuvm.test()
class RegisterReset(pyuvm.uvm_test):
    async def run_phase(self):
        self.raise_objection()
        try:
            here = Path(__file__).resolve().parent
            cfg = json.loads((here/'bindings.json').read_text())
            dut = cocotb.top
            pins = {k:getattr(dut,v) for k,v in cfg['pins'].items()}
            pins['clk'] = getattr(dut,cfg['clock'])
            pins['reset_n'] = Reset(getattr(dut,cfg['reset']),cfg['reset_active'])
            pins.setdefault('pstrb',Constant(0)); pins.setdefault('pprot',Constant(0))
            for key in ('psel','penable','paddr','pwrite','pwdata','pstrb','pprot'):
                pins[key].value = 0
            agent = CocotbAgent(SimpleNamespace(**pins))
            await start(dut)
            ral = RegisterModel(here/cfg['map'],Frontdoor(agent))
            checks = 0
            for name in cfg['registers']:
                await ral.read(name,check=True)
                checks += 1
            assert checks > 0
        finally:
            self.drop_objection()
'''
