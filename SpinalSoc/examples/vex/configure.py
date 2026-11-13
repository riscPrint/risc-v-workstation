#!/usr/bin/env python3
"""Resolve the external core and tool inputs into a local regression project."""
import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def configure(out, core, classpath=None):
    core = Path(core).resolve()
    if not (core/'src/main/scala/vexriscv/VexRiscv.scala').is_file():
        raise ValueError('core must be a VexRiscv source checkout')
    text = (HERE/'rvw.template.toml').read_text()
    text = text.replace('source_repo = "$VEXRISCV"', 'source_repo = '+json.dumps(str(core)))
    text = text.replace('adapter = "./run.sh"','adapter = '+json.dumps(str(HERE/'run.sh')))
    for relative in ['../../src','../../build.sbt','../../project/build.properties','../../../rvw/src','../../../scripts/with-lock.sh','../../programs/vex','../../../examples/vexriscv/rvw/out/isa']:
        text = text.replace(json.dumps(relative),json.dumps(str((HERE/relative).resolve())))
    text = text.replace('".",',json.dumps(str(HERE))+',',1)
    if classpath:
        paths = [Path(p).resolve() for p in classpath.strip().split(':')]
        if any(not p.exists() for p in paths):
            raise ValueError('classpath entries must exist')
        start = text.index('cache_paths = ['); end = text.index(']',start)
        text = text[:end]+', '+', '.join(json.dumps(str(p)) for p in paths)+text[end:]
        text = text.replace('input_env = [','input_env = ["RVW_SOC_CLASSPATH",')
    out = Path(out)
    if out.exists(): raise ValueError('output directory must be new')
    out.mkdir(parents=True)
    (out/'rvw.toml').write_text(text)
    return out/'rvw.toml'


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out',required=True)
    p.add_argument('--classpath-file',help='optional captured, precompiled development classpath')
    args = p.parse_args()
    cp = Path(args.classpath_file).read_text() if args.classpath_file else None
    print(configure(args.out,os.environ['VEXRISCV'],cp))
