#!/usr/bin/env python3
"""Emit standalone FP harness RTL with a completed pinned Vexii classpath."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=('lane','sqrt'),required=True)
    p.add_argument('--width',type=int,choices=(32,64),required=True)
    p.add_argument('--classpath-cache',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    core=Path(os.environ['VEXIIRISCV']).resolve()
    source=Path(__file__).with_name('FpuLaneHarness.scala' if args.kind=='lane' else 'FpuSqrtHarness.scala')
    cache=json.loads(args.classpath_cache.read_text())
    cp=cache['classpath']
    helper=Path(os.environ['RVW_HOME'])/'examples/vexiiriscv/rvw/classpath-cache.py'
    spec=importlib.util.spec_from_file_location('vexii_classpath',helper)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if module.runtime(cp)!=cache['runtime']:
        raise ValueError('compiled classpath changed; rebuild the pinned adapter first')
    plugin=core/'ext/SpinalHDL/idslplugin/target/scala-2.13/spinalhdl-idsl-plugin_2.13-dev.jar'
    classes=args.out/'classes';classes.mkdir()
    subprocess.run(['java','-Xmx2g','-cp',cp,'scala.tools.nsc.Main','-usejavacp',
                    '-Xplugin:'+str(plugin),'-d',str(classes),str(source)],check=True)
    target=args.out/'rtl';target.mkdir()
    main='rvwvexii.FpuLaneHarnessMain' if args.kind=='lane' else 'rvwvexii.FpuSqrtHarnessMain'
    subprocess.run(['java','-Xmx2g','-cp',str(classes)+os.pathsep+cp,main,str(args.width),str(target)],check=True)
    pin=subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()
    (args.out/'inputs.json').write_text(json.dumps(dict(core_revision=pin,width=args.width,kind=args.kind,
       harness_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
       classpath_cache_sha256=hashlib.sha256(args.classpath_cache.read_bytes()).hexdigest()),indent=2)+'\n')


if __name__=='__main__':main()
