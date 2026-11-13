#!/usr/bin/env python3
"""Run all generated VexRiscv checks on the aligned ISA suite in a private core."""
import argparse
import json
import os
from pathlib import Path
import sys

from rvw.common.proc import run_group
from rvw.formal.csr import generate
from rvw.checks.qualification import summarize


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True)
    p.add_argument('--timeout',type=float,default=240)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[3]
    source=Path(os.environ['VEXRISCV']).resolve()
    if not (source/'src/main/scala/vexriscv/plugin/CsrPlugin.scala').is_file():
        p.error('VEXRISCV must select a private core checkout')
    out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    model=out/'model'
    generate(root/'examples/vexriscv/csr.json',model)
    elfs=sorted(f for f in (root/'examples/vexriscv/rvw/out/isa').glob('rv32u[im]-p-*')
                if f.is_file() and f.suffix!='.dump' and f.name!='rv32ui-p-ma_data')
    if not elfs:
        p.error('build the ISA suite with rvw/build-tests.sh first')
    env=dict(os.environ,RVW_HOME=str(root),RVW_CHECKS_ISA='1')
    run=out/'native'
    command='runMain rvwvex.CsrChecksRuntime '+ ' '.join(json.dumps(str(v)) for v in
        [model/'model.json',run,'none',*elfs])
    result=run_group([str(root/'scripts/with-lock.sh'),'vex-csr',str(root/'scripts/with-lock.sh'),
        'sbt','nice','-n','10','sbt','-batch',command],cwd=root/'examples/vexriscv/rvw',
        env=env,capture=True,timeout=args.timeout)
    (out/'native.log').write_text(result.stdout+result.stderr)
    runs=sorted(run.glob('c1_*.json'))
    report=dict(status='inconclusive',expected_programs=len(elfs),completed_programs=len(runs),
        native_exit=result.returncode,timed_out=result.timed_out)
    if (run/'checks.json').exists():
        report['checks']=summarize(run/'checks.json',runs)
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 1 if result.returncode or len(runs)!=len(elfs) else 3


if __name__=='__main__': sys.exit(main())
