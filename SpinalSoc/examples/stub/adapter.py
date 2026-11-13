#!/usr/bin/env python3
"""Small C1 adapter for the explicitly bounded RV32 stub example."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('RVW_SOC_STUB_ROOT', HERE.parents[2])).resolve()
HERE = ROOT/'SpinalSoc/examples/stub'
LIB = ROOT/'SpinalSoc'


def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['identity','build','run','run-many'])
    p.add_argument('--manifest')
    p.add_argument('--jobs',type=int,default=1)
    p.add_argument('--config',default='stub')
    p.add_argument('--elf')
    p.add_argument('--out')
    p.add_argument('--seed',type=int,default=17)
    p.add_argument('--max-cycles',type=int,default=20000)
    p.add_argument('--mem-latency',type=int)
    p.add_argument('--json',action='store_true')
    args=p.parse_args()
    if args.action == 'run-many':
        if not args.manifest: p.error('run-many needs --manifest')
        failed = False
        for line in Path(args.manifest).read_text().splitlines():
            if not line.strip(): continue
            job = json.loads(line)
            argv = [sys.executable, str(Path(__file__).resolve()), 'run']
            for key, value in job.items():
                if value is None or value is False: continue
                argv += ['--'+key.replace('_','-'), str(value)]
            failed |= subprocess.run(argv).returncode != 0
        return int(failed)
    if args.config!='stub' or args.mem_latency not in (None,0):
        p.error('only config stub with fixed APB latency is supported')
    if args.action=='identity':
        h=hashlib.sha256()
        for src in sorted([*LIB.glob('src/**/*.scala'),*HERE.glob('*'),LIB/'build.sbt']):
            if src.is_file(): h.update(src.read_bytes())
        print(h.hexdigest())
        return 0
    from rvw.soc.compose import compose
    from rvw.common.proc import run_group
    snapshot = None
    if args.action == 'run':
        if not args.elf or not args.out or args.max_cycles <= 0:
            p.error('run needs --elf, --out and a positive cycle limit')
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=True)
        snapshot = out/'program.elf'
        snapshot.write_bytes(Path(args.elf).read_bytes())
    generated=LIB/'generated'
    if generated.exists(): shutil.rmtree(generated)
    compose(HERE/'compose.json',generated,snapshot)
    if args.action=='build':
        result=run_group([str(ROOT/'scripts/with-lock.sh'),os.environ.get('RVW_SBT_LOCK', 'sbt'),'nice','-n','10','sbt','-Drvw.soc.stub=true','compile'],cwd=LIB,timeout=180,capture=True)
        print(result.stdout)
        print(result.stderr,file=sys.stderr)
        return result.returncode
    if not args.elf or not args.out or args.max_cycles<=0:
        p.error('run needs --elf, --out and a positive cycle limit')
    out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    env = dict(os.environ)
    if env.get('RVW_CHECKS_ISA') == '1':
        env.update(RVW_SOC_CHECKS_OUT=str(out),
                   RVW_SOC_CHECKS_ELF_SHA=hashlib.sha256(snapshot.read_bytes()).hexdigest())
    result=run_group([str(ROOT/'scripts/with-lock.sh'),os.environ.get('RVW_SBT_LOCK', 'sbt'),'nice','-n','10','sbt','-Drvw.soc.stub=true',f'runMain example.Run {args.seed} {args.max_cycles}'],cwd=LIB,timeout=240,capture=True,env=env)
    log=(result.stdout or '')+'\n'+(result.stderr or '')
    (out/'run.log').write_text(log)
    measurements=None
    for line in log.splitlines():
        if 'SOC_RESULT ' in line:
            measurements=json.loads(line.split('SOC_RESULT ',1)[1])
    if result.returncode or not measurements:
        measurements=dict(status='error',cycles=0,instret=0,fail_code=None,message='native run did not complete; see run.log')
    if Path(args.elf).name == 'hello' and measurements.get('status') == 'pass' and measurements.get('uart') != 'hello\n':
        measurements.update(status='fail', message='UART output differs from hello newline')
    rtl=hashlib.sha256()
    for src in sorted((LIB/'simWorkspace').glob('tmp/job_1/*')):
        if src.is_file():
            rtl.update(src.name.encode());rtl.update(src.read_bytes())
    rev=git('rev-parse','HEAD')
    dirty=bool(git('status','--porcelain'))
    source=dict(core_repo=str(ROOT),core_rev=rev[:12],core_rev_full=rev,core_dirty=dirty,
                tools_repo=str(ROOT),tools_rev=rev,tools_dirty=dirty)
    report=dict(schema='rvw.run/1',core='soc-stub',config='stub',elf=str(Path(args.elf).resolve()),
                elf_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),rtl_sha256=rtl.hexdigest(),
                seed=args.seed,max_cycles=args.max_cycles,mem_latency=args.mem_latency,
                status=measurements['status'],cycles=measurements['cycles'],instret=measurements['instret'],
                fail_code=None if measurements['status']=='pass' else measurements['fail_code'],message=measurements.get('message'),wall_s=time.monotonic()-start,
                source=source,tools=dict(spinalhdl='1.15.0',verilator=subprocess.check_output(['verilator','--version'],text=True).strip()),artifacts=dict(log='run.log'),
                replay=f'{HERE}/run.sh run --elf {Path(args.elf).resolve()} --out REPLAY --seed {args.seed} --max-cycles {args.max_cycles}',
                details=dict(profile='rv32-stub-word-apb3',uart=measurements.get('uart',''), external_source_at_cycle=200))
    if env.get('RVW_CHECKS_ISA') == '1':
        observed = json.loads((out/'checks-run.json').read_text()) if (out/'checks-run.json').is_file() else None
        if observed is None:
            report.update(status='error', message='generated check observations are missing')
        elif observed['status'] != 'pass' and report['status'] == 'pass':
            report.update(status='fail', message='generated checks fired')
        report['artifacts'].update(inventory='checks.json', checks='checks-run.json')
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['status']=='pass' else 1


if __name__=='__main__':
    raise SystemExit(main())
