"""Database-selected project bench profiles with explicit scenario hooks.

Bus structure does not specify peripheral semantics. Generated tests refuse to
pass until a project supplies its scenario and a positive check count.
"""
import json
from pathlib import Path
from rvw.query.db import DesignDB

PROFILES = ('cpu', 'apb', 'axi', 'axi-lite', 'tilelink', 'axis', 'uart', 'spi', 'i2c')

def classify(class_name):
    leaf = class_name.rsplit('.',1)[-1].split('$')[0]
    names = {'Apb3':'apb','Apb4':'apb','Axi4':'axi','AxiLite4':'axi-lite',
             'Axi4Stream':'axis','Tilelink':'tilelink','Uart':'uart',
             'SpiMaster':'spi','SpiSlave':'spi','I2c':'i2c','I2cMaster':'i2c','Rvfi':'cpu'}
    if leaf=='Bus' and '.tilelink.' in class_name: return 'tilelink'
    return names.get(leaf)


def generate(db, soc, out, *, rtl=None, language='pyuvm', profile='auto', adapter=None):
    project = None
    if adapter is not None:
        adapter = Path(adapter).resolve()
        project = json.loads(adapter.read_text())
        if project.get('schema') != 'rvw.uvm-adapter/1' or project.get('profile') not in PROFILES:
            raise ValueError('expected rvw.uvm-adapter/1 and a supported agent profile')
        if language != 'pyuvm':
            raise ValueError('project adapters currently require pyuvm')
        scenario = (adapter.parent / project['scenario']).resolve().read_text()
        if not isinstance(project.get('bindings'), dict):
            raise ValueError('adapter bindings must be an object')
    if language not in ('pyuvm','sv'): raise ValueError('language must be pyuvm or sv')
    if profile not in ('auto', *PROFILES): raise ValueError('unknown UVM profile: '+profile)
    from rvw.soc.model import load
    db,soc,out = Path(db).resolve(),Path(soc).resolve(),Path(out).resolve()
    load(soc)
    design = DesignDB(db)
    try:
        tops=list(design.conn.execute('SELECT id,module FROM components WHERE parent_id IS NULL'))
        if len(tops)!=1: raise ValueError('profile requires one top component')
        component,top=tops[0]
        buses=[dict(path=p,spinal_type=c,profile=classify(c)) for p,c in design.conn.execute(
            'SELECT path,class_name FROM bundles WHERE component_id=?',(component,)) if classify(c)]
        if project is not None:
            declared = design.conn.execute('SELECT path FROM bundles WHERE component_id=?', (component,)).fetchall()
            if project['bus'] not in {p for p, in declared}:
                raise ValueError('project adapter bus is not in the top-level database bundles')
            buses = [dict(path=project['bus'], class_name='project-owned', profile=project['profile'])]
            profile = project['profile']
        matches=buses if profile=='auto' else [b for b in buses if b['profile']==profile]
        if len(matches)!=1: raise ValueError('select one database bus with --profile; found '+json.dumps(buses))
        selected=matches[0]; profile=selected['profile']
        ports=[dict(name=n,direction=d) for n,d in design.conn.execute(
            'SELECT name,direction FROM signals WHERE component_id=? AND direction IS NOT NULL',(component,))]
        domains=[dict(clock=c,reset=r,reset_active_high=a) for c,r,a in design.conn.execute(
            'SELECT DISTINCT clock,reset,reset_active_high FROM clock_domains WHERE clock IS NOT NULL AND reset IS NOT NULL')]
        sources=list(rtl) if rtl else [p for p, in design.conn.execute('SELECT path FROM rtl_files')]
    finally: design.close()
    sources=[str((db.parent/Path(p)).resolve(strict=True)) for p in sources]
    if not sources: raise ValueError('no RTL files; supply --rtl')
    root=Path(__file__).resolve().parents[4]
    agent='axi' if profile=='axi-lite' else profile
    support=root/'Uvm'/('cpu' if profile=='cpu' else 'vip/'+agent)
    if not support.is_dir(): raise ValueError('profile support is not installed: '+str(support))
    config=dict(profile=profile,language=language,bus=selected,ports=ports,
                clock_domains=domains,map='map.json',support=str(support),
                scenario_required=True)
    if project is not None:
        config['project_adapter'] = project
    out.mkdir(parents=True,exist_ok=False)
    (out/'bindings.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'map.json').write_text(soc.read_text())
    if language=='pyuvm':
        module='rvw.sim.cpu_env' if profile=='cpu' else 'rvw.vip.'+agent
        (out/'test_generated.py').write_text(PYTHON.replace('AGENT_MODULE',module))
        (out/'scenario.py').write_text(scenario if project is not None else SCENARIO)
        manifest=dict(schema='rvw.cocotb/1',name='generated_'+profile.replace('-','_'),
            backend='verilator',top=top,sources=sources,test_module='test_generated',python_paths=['.'],requires=['timer'])
    else:
        (out/'project_scenario.svh').write_text('`uvm_fatal("PROJECT_SCENARIO_REQUIRED", "bind the selected agent and add checked stimulus")\n')
        (out/'generated.sv').write_text(SV)
        manifest=dict(schema='rvw.uvm/1',name='generated_'+profile.replace('-','_'),
            top='generated_top',sources=[*sources,str(out/'generated.sv')],include_dirs=['.'],tests=['generated_test'],bindings=config)
    (out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'README.md').write_text(f'''Generated {profile} {language} project profile.

The selected bus, top ports and clock domains come from the design database.
Agent support: {support}

Supply project wire bindings, reset and stimulus in the scenario hook.
The generated test refuses to pass until the hook performs positive checks.
Spinal bus types do not define the device behavior or reference expectations.
CPU profiles require an ELF, a matched Spike reference and checked completion.
Serial profiles require framing, role and expected device behavior.
SV profiles require a DUT instance and the selected VIP virtual interface.
The generated SV wrapper deliberately has no completion marker before binding.
No native qualification or C4 acceptance follows from profile generation.
''')
    return dict(out=str(out),manifest=str(out/'bench.json'),profile=profile,language=language,
                scenario_required=True,agents=[selected])

PYTHON='''import json
import importlib
from pathlib import Path
import cocotb
import pyuvm
from scenario import run

class Services:
    def __init__(self, dut, config):
        self.dut, self.config = dut, config
        self.agent_module = importlib.import_module('AGENT_MODULE')
        self.checks = 0
    def checked(self, condition, message):
        assert condition, message
        self.checks += 1

@pyuvm.test()
class GeneratedProfile(pyuvm.uvm_test):
    async def run_phase(self):
        self.raise_objection()
        try:
            config=json.loads((Path(__file__).parent/'bindings.json').read_text())
            services=Services(cocotb.top,config)
            await run(services)
            assert services.checks > 0, 'PROJECT_NO_CHECKS'
        finally:
            self.drop_objection()
'''
SCENARIO='''async def run(services):
    # Bind services.agent_module.CocotbAgent to the selected database bus.
    # Drive reset and checked traffic. Use services.checked for actual checks.
    # CPU profiles use CpuMemory and CpuScoreboard with independent Spike.
    raise RuntimeError('PROJECT_SCENARIO_REQUIRED: bind pins and expected behavior')
'''
SV='''package generated_pkg;
 import uvm_pkg::*;
 `include "uvm_macros.svh"
 class generated_test extends uvm_test;
  `uvm_component_utils(generated_test)
  int checks=0;
  function new(string name="generated_test", uvm_component parent=null);
   super.new(name,parent);
  endfunction
  task run_phase(uvm_phase phase);
   phase.raise_objection(this);
   `include "project_scenario.svh"
   if(checks<=0) `uvm_fatal("PROJECT_NO_CHECKS","no checked activity")
   phase.drop_objection(this);
  endtask
  function void report_phase(uvm_phase phase);
   if(checks>0 && uvm_report_server::get_server().get_severity_count(UVM_ERROR)==0 &&
      uvm_report_server::get_server().get_severity_count(UVM_FATAL)==0)
    $display("RVW_UVM_DONE generated_test checks=%0d",checks);
  endfunction
 endclass
endpackage
module generated_top;
 import uvm_pkg::*;
 import generated_pkg::*;
 initial begin
  uvm_top.set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
  run_test("generated_test");
 end
 initial begin #100000; $fatal(1,"PROJECT_WATCHDOG"); end
endmodule
'''
