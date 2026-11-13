#!/usr/bin/env python3
"""C1 adapter for the fixed-seed command fixture, including one ROB-head flip."""
import argparse
import os
from pathlib import Path
import shutil
from rvw.common.proc import run_group


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['run'])
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--elf',required=True)
    parser.add_argument('--fault',type=Path)
    args,_=parser.parse_known_args()
    here=Path(__file__).resolve().parent
    root=here.parents[2]
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,RVW_OOO_RUN_ROOT=str(out/'native'))
    if args.fault:env['RVW_OOO_FAULT']=str(args.fault.resolve())
    run=run_group([str(root/'scripts/with-lock.sh'),'sbt-csr','nice','-n','15',
        'sbt','-batch','runMain spinalchecks.examples.ooo.Run clean'],cwd=here,env=env,capture=True,timeout=110)
    (out/'native.log').write_text(run.stdout+run.stderr)
    for file in (out/'native/clean').glob('*'):
        if file.is_file():shutil.copyfile(file,out/file.name)
    return 0 if (out/'result.json').exists() else 2


if __name__=='__main__':
    raise SystemExit(main())
