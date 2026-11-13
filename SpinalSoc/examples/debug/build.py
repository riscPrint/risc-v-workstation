#!/usr/bin/env python3
"""Build the composed DMI and JTAG profiles from the existing Vex debug configs."""
import argparse
import json
import os
from pathlib import Path
from rvw.common.proc import run_group
from rvw.soc.compose import compose
from rvw.soc.peripherals import peripheral

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)

def run(argv,name,cwd=ROOT):
    with (out/(name+'.log')).open('w') as log:r=run_group(argv,cwd=cwd,stdout=log,stderr=log,timeout=120)
    if r.returncode or r.timed_out:raise SystemExit('Build failed: '+name+'.log')

run(['nice','-n','10',os.environ.get('RISCV_PREFIX','riscv64-unknown-elf-')+'gcc','-march=rv32im_zicsr','-mabi=ilp32',
     '-nostdlib','-nostartfiles','-T',str(HERE/'../stub/link.ld'),str(HERE/'loop.S'),'-o',str(out/'loop.elf')],'program')
files=[HERE/'DebugCore.scala',ROOT/'SpinalProbes/src/main/scala/spinalprobes/Probe.scala',ROOT/'RiscvSim/src/main/scala/riscvsim/LockstepDpi.scala']
files += [ROOT/'examples/vexriscv/rvw/src/main/scala/rvwvex'/n for n in ('VexTop.scala','DebugTop.scala','CachedConfig.scala','ProbePlugin.scala','TraceIngressPlugin.scala','CacheProbes.scala')]
for profile in ('dmi','jtag'):
    case=out/profile;case.mkdir()
    model=json.loads((HERE/'../vex/soc.json').read_text());model['interrupts']=[]
    model['regions']=[dict(name='ram',kind='ram',base=0x80000000,size=65536,permissions='rwx',cacheable=False,registers=[]),peripheral('gpio','gpio',0x10000000)['region']]
    (case/'map.json').write_text(json.dumps(model))
    spec=dict(schema='rvw.soc-compose/1',map='map.json',clock_hz=50000000,reset='async_high',
              core={'class':'examplesocdebug.'+('DmiCore' if profile=='dmi' else 'JtagCore'),'bus':'axi4','exports':['retired']},
              devices=dict(ram=dict(type='ram'),gpio=dict(type='project',**{'class':'rvwsoc.Gpio'},exports=['input','output'])))
    (case/'compose.json').write_text(json.dumps(spec));compose(case/'compose.json',case/'composition',out/'loop.elf')
    scala=case/'composition/ComposedSoc.scala';top=profile.capitalize()+'Soc'
    text=scala.read_text().replace('ComposedSoc',top).replace('object Generate','object '+profile.capitalize()+'Generate')
    text=text.replace('  core.debugReset := False','  core.debugReset := False\n  val debug_'+profile+'=core.'+profile+'.toIo()\n  val debug_ndmreset=core.ndmreset.toIo()')
    scala.write_text(text);files.append(scala)
setting='set Compile / unmanagedSources ++= Seq('+','.join('file("'+str(f)+'")' for f in files)+')'
run([str(ROOT/'scripts/with-lock.sh'),'sbt-soc','nice','-n','10','sbt','-J-XX:ActiveProcessorCount=4','-J-Xmx3g','-Drvw.soc.vex=true',
     'set libraryDependencies += "com.lihaoyi" %% "ujson" % "3.3.1"',setting,'compile','export Compile/fullClasspath'],'compile',ROOT/'SpinalSoc')
cp=next(line for line in reversed((out/'compile.log').read_text().splitlines()) if 'scala-2.13/classes:' in line and not line.startswith('['))
for profile in ('dmi','jtag'):
    case=out/profile;top=profile.capitalize()+'Soc'
    run(['nice','-n','10','java','-cp',cp,'generated.'+profile.capitalize()+'Generate',str(case/'rtl')],profile+'-elaborate')
    rtl=case/'rtl'/(top+'.v');text=rtl.read_text()
    for image in (case/'rtl').glob('*.bin'):text=text.replace('"'+image.name+'"','"'+str(image)+'"')
    rtl.write_text(text)
    manifest=dict(schema='rvw.cocotb/1',name='composed_'+profile,backend='verilator',top=top,sources=[str(rtl)],test_module='test_debug',python_paths=[str(HERE)],requires=['timer'],clock=dict(signal='clk',period_ns=20),reset=dict(signal='reset',active=1,cycles=5))
    (case/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(out)
