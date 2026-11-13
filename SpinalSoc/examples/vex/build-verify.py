#!/usr/bin/env python3
"""Build the two composed tops and capture their private development classpath."""
from pathlib import Path
import shutil

from rvw.common.proc import run_group
from rvw.soc.compose import compose

root = Path(__file__).resolve().parents[3]
here = Path(__file__).resolve().parent
library = root/'SpinalSoc'
out = library/'out'
out.mkdir(exist_ok=True)
for name, spec in [('ComposedSoc','compose.json'), ('MultiDomainSoc','compose-multidomain.json')]:
    target = out/('verify-source-'+name)
    if target.exists():
        shutil.rmtree(target)
    compose(here/spec,target)
    text = (target/'ComposedSoc.scala').read_text()
    if name != 'ComposedSoc':
        text = text.replace('ComposedSoc',name).replace('object Generate','object MultiDomainGenerate')
    (library/'generated').mkdir(exist_ok=True)
    (library/'generated'/f'{name}.scala').write_text(text)
command = [str(root/'scripts/with-lock.sh'),'sbt-soc','nice','-n','10','sbt','-J-XX:ActiveProcessorCount=4','-J-Xmx3g',
           '-Drvw.soc.vex=true','db/compile','export db/Compile/fullClasspath']
with (out/'verify-db-build.log').open('w') as log:
    process = run_group(command,cwd=library,stdout=log,stderr=log,timeout=240)
if process.returncode or process.timed_out:
    raise SystemExit('Build failed; see SpinalSoc/out/verify-db-build.log')
lines = (out/'verify-db-build.log').read_text().splitlines()
classpath = next(line for line in reversed(lines) if 'scala-2.13/classes:' in line and not line.startswith('['))
for name in ('database-cp.txt','vex-cp.txt'):
    (out/name).write_text(classpath+'\n')
