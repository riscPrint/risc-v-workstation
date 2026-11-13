#!/usr/bin/env python3
"""Build a ROM-only preload and an SPI-only payload for the composed CPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from rvw.common.proc import run_group
from rvw.soc.compose import compose
from rvw.soc.peripherals import peripheral

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args()
out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
core=Path(os.environ['VEXRISCV'])
if not (core/'src/main/scala/vexriscv/VexRiscv.scala').is_file():
    raise SystemExit('Missing input: private VEXRISCV source checkout')
cc=os.environ.get('RISCV_PREFIX','riscv64-unknown-elf-')+'gcc'
objcopy=os.environ.get('RISCV_PREFIX','riscv64-unknown-elf-')+'objcopy'

def run(argv,name,cwd=ROOT,timeout=120):
    with (out/(name+'.log')).open('w') as log:
        result=run_group(argv,cwd=cwd,stdout=log,stderr=log,timeout=timeout)
    if result.returncode or result.timed_out:
        raise SystemExit('Build failed: '+name+'.log')

for name,base in [('payload',0x80010000),('boot',0x80000000)]:
    linker=out/(name+'.ld')
    linker.write_text(f'ENTRY(_start)\nSECTIONS {{ . = 0x{base:x}; .text : {{ *(.text*) }} }}\n')
    command=['nice','-n','10',cc,'-march=rv32im_zicsr_zifencei','-mabi=ilp32','-nostdlib','-nostartfiles','-T',str(linker)]
    if name=='boot':command += [f'-DAPP_SIZE={len(payload)}',f'-DAPP_SUM={sum(payload)}']
    run([*command,str(HERE/(name+'.S')),'-o',str(out/(name+'.elf'))],name)
    if name=='payload':
        run([objcopy,'-O','binary',str(out/'payload.elf'),str(out/'payload.bin')],'payload-binary')
        payload=(out/'payload.bin').read_bytes()
        if not payload or len(payload)>4096:raise SystemExit('Payload must contain 1 to 4096 bytes')
flash=bytes([255])*256+payload
(out/'flash.bin').write_bytes(flash)
model=json.loads((HERE/'../vex/soc.json').read_text())
model['name']='spi_flash_boot';model['interrupts']=[]
model['regions']=[dict(name='bootrom',kind='ram',base=0x80000000,size=4096,permissions='rx',cacheable=False,registers=[]),
                  dict(name='ram',kind='ram',base=0x80010000,size=65536,permissions='rwx',cacheable=False,registers=[])]
spi=peripheral('spi','spi',0x10000000)
finisher=peripheral('finisher','finisher',0x10001000)
model['regions'] += [spi['region'],finisher['region']]
(out/'map.json').write_text(json.dumps(model))
spec=dict(schema='rvw.soc-compose/1',map='map.json',core={'class':'examplesocvex.VexCore','bus':'axi4','exports':['retired']},
          clock_hz=50000000,reset='async_high',devices=dict(bootrom=dict(type='rom'),ram=dict(type='ram'),
          spi=dict(spi['binder'],exports=['pins']),finisher=dict(finisher['binder'],exports=['done','code'])))
(out/'compose.json').write_text(json.dumps(spec))
compose(out/'compose.json',out/'composition',out/'boot.elf')
scala=out/'composition/ComposedSoc.scala'
text=scala.read_text().replace('ComposedSoc','FlashBootSoc').replace('object Generate','object FlashBootGenerate')
# This observation adds no driver or preload to the RAM.
text=text.replace('\n}\nobject FlashBootGenerate','\n  val ramWord0 = ram.rework { val word = out Bits(32 bits); word.setName("bootWord0"); word := ram.mem.readAsync(U(0, 14 bits)); word }\n  val boot_ram_word0 = out Bits(32 bits)\n  boot_ram_word0 := ramWord0\n}\nobject FlashBootGenerate')
scala.write_text(text)
# Check that the generated constructor has no application RAM preload.
if 'val ram = new WordMemory(16, 16384, false, Seq(), byteWrites = true)' not in text:
    raise SystemExit('RAM must start empty; payload may only enter through SPI')
run([str(ROOT/'scripts/with-lock.sh'),'sbt-soc','nice','-n','10','sbt','-J-XX:ActiveProcessorCount=4','-J-Xmx3g',
     '-Drvw.soc.vex=true','set Compile / unmanagedSources += file("'+str(scala)+'")','compile',
     'export Compile/fullClasspath'],'compile',cwd=ROOT/'SpinalSoc')
lines=(out/'compile.log').read_text().splitlines()
cp=next(line for line in reversed(lines) if 'scala-2.13/classes:' in line and not line.startswith('['))
(out/'classpath.txt').write_text(cp+'\n')
run(['nice','-n','10','java','-cp',cp,'generated.FlashBootGenerate',str(out/'rtl')],'elaborate')
# Bind any backend memory files to this exact run directory.
rtl=out/'rtl/FlashBootSoc.v';text=rtl.read_text()
images={}
for image in (out/'rtl').glob('*.bin'):
    images[image.name]=hashlib.sha256(image.read_bytes()).hexdigest()
    text=text.replace('"'+image.name+'"','"'+str(image)+'"')
rtl.write_text(text)
shutil.copyfile(HERE/'test_boot.py',out/'test_boot.py')
settings=dict(core_revision=subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip(),
              tools_revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
              payload_size=len(payload),payload_sha256=hashlib.sha256(payload).hexdigest(),
              flash_sha256=hashlib.sha256(flash).hexdigest(),boot_sha256=hashlib.sha256((out/'boot.elf').read_bytes()).hexdigest(),
              first_word=int.from_bytes(payload[:4],'little'),memory_images=images,max_cycles=50000)
(out/'boot.json').write_text(json.dumps(settings,indent=2)+'\n')
manifest=dict(schema='rvw.cocotb/1',name='spi_flash_boot',backend='verilator',top='FlashBootSoc',sources=[str(rtl)],
              test_module='test_boot',python_paths=['.'],requires=['timer'],clock=dict(signal='clk',period_ns=20),
              reset=dict(signal='reset',active=1,cycles=5))
(out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(out/'bench.json')
