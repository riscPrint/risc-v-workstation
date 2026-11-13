#!/usr/bin/env python3
"""Compose a pinned external UART through its declared Wishbone interface."""
import argparse
import json
from pathlib import Path
from rvw.common.proc import run_group
from rvw.soc.compose import compose
from rvw.soc.ip_import import import_ip

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
imported=import_ip(HERE/'uart.toml',a.root,out/'ip',0x10000000)
model=json.loads((HERE/'../vex/soc.json').read_text());model['interrupts']=[]
model['regions']=[dict(name='ram',kind='ram',base=0x80000000,size=4096,permissions='rwx',cacheable=False,registers=[]),imported['region']]
(out/'map.json').write_text(json.dumps(model))
spec=dict(schema='rvw.soc-compose/1',map='map.json',clock_hz=50000000,reset='async_high',
          core={'class':'rvwsoc.VerificationCore','bus':'simple','exports':['stimulus']},
          devices=dict(ram=dict(type='ram'),external_uart=imported['binder']))
(out/'compose.json').write_text(json.dumps(spec));compose(out/'compose.json',out/'composition')
scala=out/'composition/ComposedSoc.scala'
scala.write_text(scala.read_text().replace('ComposedSoc','ImportedSoc').replace('object Generate','object ImportedGenerate'))
with (out/'compile.log').open('w') as log:
    r=run_group([str(ROOT/'scripts/with-lock.sh'),'sbt-soc','nice','-n','10','sbt','-J-XX:ActiveProcessorCount=4','-J-Xmx3g','-Drvw.soc.vex=true',
        'set Compile / unmanagedSources ++= Seq(file("'+str(scala)+'"),file("'+str(out/'ip/external_uart.scala')+'"))',
        'compile','export Compile/fullClasspath'],cwd=ROOT/'SpinalSoc',stdout=log,stderr=log,timeout=120)
if r.returncode or r.timed_out:raise SystemExit('Build failed: compile.log')
cp=next(s for s in reversed((out/'compile.log').read_text().splitlines()) if 'scala-2.13/classes:' in s and not s.startswith('['))
with (out/'elaborate.log').open('w') as log:r=run_group(['nice','-n','10','java','-cp',cp,'generated.ImportedGenerate',str(out/'rtl')],cwd=ROOT,stdout=log,stderr=log,timeout=120)
if r.returncode or r.timed_out:raise SystemExit('Build failed: elaborate.log')
rtl=out/'rtl/ImportedSoc.v';text=rtl.read_text()
for image in (out/'rtl').glob('*.bin'):text=text.replace('"'+image.name+'"','"'+str(image)+'"')
rtl.write_text(text)
manifest=dict(schema='rvw.cocotb/1',name='imported_uart',backend='icarus',top='ImportedSoc',sources=[str(rtl),str(out/'ip/bridge.v'),str(out/'ip/bundle.v')],test_module='test_import',python_paths=[str(HERE)],requires=['timer'],clock=dict(signal='clk',period_ns=20),reset=dict(signal='reset',active=1,cycles=5))
(out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(out/'bench.json')
