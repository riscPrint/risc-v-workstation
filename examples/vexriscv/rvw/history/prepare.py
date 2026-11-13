#!/usr/bin/env python3
"""Prepare two real historical example revisions outside the checkout."""
import argparse
import json
import os
from pathlib import Path
import shutil
from rvw.common.proc import run_group

GOOD='78ba8c540cb0f81030936cefce2faaf6abd65fd7'
BAD='6c891a7615b843308e94efb4b4ff5551177f3bda'
HERE=Path(__file__).resolve().parent


def command(argv,timeout=60):
    r=run_group(list(map(str,argv)),timeout=timeout,capture=True)
    if r.returncode or r.timed_out:raise ValueError(r.stdout+r.stderr)
    return r.stdout.strip()


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--classpath',type=Path,required=True)
    p.add_argument('--compiler-jars',nargs=3,type=Path,required=True);p.add_argument('--plugin',type=Path,required=True)
    args=p.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    repo=HERE.parents[3]
    command(['git','clone','--quiet','--no-hardlinks','--no-checkout',repo,out/'source'])
    command(['git','-C',out/'source','checkout','--quiet',BAD])
    harness=out/'harness';shutil.copytree(HERE,harness,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(HERE.parent/'engine-probe.py',harness/'engine_probe.py')
    settings=dict(good=GOOD,bad=BAD,java=shutil.which('java'),classpath=args.classpath.read_text().strip(),
                  compiler_jars=[str(p.resolve(strict=True)) for p in args.compiler_jars],plugin=str(args.plugin.resolve(strict=True)))
    (harness/'settings.json').write_text(json.dumps(settings,indent=2)+'\n')
    doc=dict(schema='rvw.adapter-versions/1',revisions={GOOD:'legacy',BAD:'m-only'},adapters={
        'legacy':dict(api=1,command=['legacy.sh']),'m-only':dict(api=1,command=['m_only.sh'])})
    (harness/'adapters.json').write_text(json.dumps(doc,indent=2)+'\n')
    (harness/'debug.toml').write_text('[core]\nsource_env="RVW_HISTORY_SOURCE"\nadapter_versions="adapters.json"\n')
    gcc=os.environ.get('RISCV_PREFIX','riscv64-unknown-elf-')+'gcc'
    command([gcc,'-march=rv32im_zicsr_zifencei','-mabi=ilp32','-nostdlib','-nostartfiles',
             '-T',HERE.parent/'programs/link.ld',HERE/'csr-transition.S','-o',out/'csr-transition.elf'])
    print(json.dumps(dict(source=str(out/'source'),harness=str(harness),elf=str(out/'csr-transition.elf'),good=GOOD,bad=BAD)))

if __name__=='__main__':main()
