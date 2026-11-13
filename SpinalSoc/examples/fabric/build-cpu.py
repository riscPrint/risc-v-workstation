#!/usr/bin/env python3
"""Build the optional CPU + DMA-style native AXI composition."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from rvw.common.proc import run_group
from rvw.soc.compose import compose
from rvw.soc.peripherals import peripheral

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);args=p.parse_args()
out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)

def run(argv,name,cwd=ROOT):
    with (out/(name+'.log')).open('w') as log:
        result=run_group(argv,cwd=cwd,stdout=log,stderr=log,timeout=120)
    if result.returncode or result.timed_out:raise SystemExit('Build failed: '+name+'.log')

run(['nice','-n','10',os.environ.get('RISCV_PREFIX','riscv64-unknown-elf-')+'gcc',
     '-march=rv32im_zicsr','-mabi=ilp32','-nostdlib','-nostartfiles','-T',str(HERE/'../stub/link.ld'),
     str(HERE/'cpu.S'),'-o',str(out/'cpu.elf')],'program')
model=json.loads((HERE/'../vex/soc.json').read_text())
model['name']='cpu_dma';model['interrupts']=[]
model['regions']=[dict(name='ram',kind='ram',base=0x80000000,size=65536,permissions='rwx',cacheable=False,registers=[]),
                  peripheral('finisher','finisher',0x10001000)['region']]
(out/'map.json').write_text(json.dumps(model))
spec=dict(schema='rvw.soc-compose/1',map='map.json',clock_hz=50000000,reset='async_high',
    core={'class':'examplesocdma.VexDmaCore','bus':'axi4','exports':['retired','dmaDone','dmaError','dmaWrites','dmaReads']},
    devices=dict(ram=dict(type='ram'),finisher=dict(type='project',**{'class':'rvwsoc.Finisher'},exports=['done','code'])))
(out/'compose.json').write_text(json.dumps(spec))
compose(out/'compose.json',out/'composition',out/'cpu.elf')
scala=out/'composition/ComposedSoc.scala'
scala.write_text(scala.read_text().replace('ComposedSoc','CpuDmaSoc').replace('object Generate','object CpuDmaGenerate'))
run([str(ROOT/'scripts/with-lock.sh'),'sbt-soc','nice','-n','10','sbt','-J-XX:ActiveProcessorCount=4','-J-Xmx3g',
     '-Drvw.soc.vex=true','set Compile / unmanagedSources ++= Seq(file("'+str(scala)+'"), file("'+str(HERE/'VexDma.scala')+'"))',
     'compile','export Compile/fullClasspath'],'compile',cwd=ROOT/'SpinalSoc')
cp=next(line for line in reversed((out/'compile.log').read_text().splitlines()) if 'scala-2.13/classes:' in line and not line.startswith('['))
(out/'classpath.txt').write_text(cp+'\n')
run(['nice','-n','10','java','-cp',cp,'generated.CpuDmaGenerate',str(out/'rtl')],'elaborate')
rtl=out/'rtl/CpuDmaSoc.v';text=rtl.read_text();images={}
for image in (out/'rtl').glob('*.bin'):
    images[image.name]=hashlib.sha256(image.read_bytes()).hexdigest()
    text=text.replace('"'+image.name+'"','"'+str(image)+'"')
rtl.write_text(text)
(out/'images.json').write_text(json.dumps(images))
manifest=dict(schema='rvw.cocotb/1',name='cpu_dma',backend='verilator',top='CpuDmaSoc',sources=[str(rtl)],
    test_module='test_cpu',python_paths=[str(HERE)],requires=['timer'],clock=dict(signal='clk',period_ns=20),
    reset=dict(signal='reset',active=1,cycles=5))
(out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(out/'bench.json')
