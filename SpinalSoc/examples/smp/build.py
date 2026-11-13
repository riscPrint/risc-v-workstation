#!/usr/bin/env python3
"""Build the optional SMP peripheral host against pinned private dependencies."""
import argparse
import importlib.util
import json
from pathlib import Path
from rvw.common.proc import run_group
from rvw.soc.compose import compose
from rvw.soc.peripherals import peripheral

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
p.add_argument('--classpath-file',type=Path,required=True)
p.add_argument('--idsl-plugin',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
cp=a.classpath_file.read_text().strip()

def run(argv,name):
    with (out/(name+'.log')).open('w') as log:r=run_group(argv,cwd=ROOT,stdout=log,stderr=log,timeout=120)
    if r.returncode or r.timed_out:raise SystemExit('Build failed: '+name+'.log')

# Reuse the existing per-hart linker and image builder without changing it.
spec=importlib.util.spec_from_file_location('smp_programs',ROOT/'examples/smp/rvw/programs.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sources=[]
for h in range(2):
    source=out/f'hart-{h}.S'
    text=m.assembly(h,'smoke')
    text=text.replace('li a0, 1',f'li t3, {0x600d0000+h}\nsd t3, 0(s0)\nld t4, 0(s0)\nbne t3, t4, fail\nli t0, {0x10000000+h*0x100}\nli t1, {0x12340000+h}\nsw t1, 4(t0)\nlwu t2, 4(t0)\nbne t1, t2, fail\nli a0, 1')
    source.write_text(text);sources.append(text)
m.build(out/'programs',sources=sources)
model=json.loads((HERE/'../vex/soc.json').read_text())
model.update(name='smp_peripheral_host',interrupts=[])
model['platform'].update(name='cacheless_smp',xlen=64,isa='rv64ima_zicsr_zifencei',reference_isa='rv64ima_zicsr_zifencei')
regions=[peripheral('gpio',f'gpio{h}',0x10000000+h*0x100)['region'] for h in range(2)]
model['regions']=[dict(name='shared_ram',kind='ram',base=0x80000000,size=0x2000000,permissions='rwx',cacheable=False,registers=[])]+regions
(out/'map.json').write_text(json.dumps(model))
composition=dict(schema='rvw.soc-compose/1',map='map.json',clock_hz=100000000,reset='async_high',
    core={'class':'examplesocsmp.SmpHost','bus':'simple','exports':['retired','mmio']},
    devices=dict(shared_ram=dict(type='host'),**{f'gpio{h}':dict(type='project',**{'class':'rvwsoc.Gpio'},exports=['output','outputEnable','input']) for h in range(2)}))
(out/'compose.json').write_text(json.dumps(composition));compose(out/'compose.json',out/'composition')
scala=out/'composition/ComposedSoc.scala';text=scala.read_text()
text=text.replace('class ComposedSoc extends Component {','''class SmpSoc extends Component {
  val ports = spinal.core.fiber.Fiber patch new Area {
    val fetch = core.area.memory.fetch.toIo()
    val lsu = core.area.memory.lsu.toIo()
  }''').replace('new ComposedSoc','new SmpSoc').replace('object Generate','object SmpGenerate')
scala.write_text(text)
files=[scala,HERE/'SmpHost.scala',ROOT/'examples/smp/rvw/src/main/scala/rvwsmp/VexiiTop.scala']
files += [ROOT/'SpinalSoc/src/main/scala/rvwsoc'/name for name in ('Soc.scala','SimpleBus.scala','Buses.scala','Peripherals.scala','Serial.scala','ProtocolChecks.scala')]
files += [ROOT/'SpinalChecks/src/main/scala/spinalchecks'/name for name in ('ProtocolChecks.scala','AxiReadChecks.scala','AxiWriteChecks.scala','TileLinkProbeChecks.scala','BusAssertions.scala','SpinalCompat.scala')]
files += [ROOT/'RiscvSim/src/main/scala/riscvsim/LockstepDpi.scala']
classes=out/'classes';classes.mkdir()
run(['nice','-n','10','java','-cp',cp,'scala.tools.nsc.Main','-usejavacp','-Xplugin:'+str(a.idsl_plugin.resolve()),'-d',str(classes),*map(str,files)],'compile')
run(['nice','-n','10','java','-cp',str(classes)+':'+cp,'generated.SmpGenerate',str(out/'rtl')],'elaborate')
manifest=dict(schema='rvw.cocotb/1',name='smp_host',backend='verilator',top='SmpSoc',sources=[str(out/'rtl/SmpSoc.v')],
    test_module='test_host',python_paths=[str(HERE)],requires=['timer'],clock=dict(signal='clk',period_ns=10),reset=dict(signal='reset',active=1,cycles=5))
(out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(out/'bench.json')
