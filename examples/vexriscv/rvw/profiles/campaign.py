#!/usr/bin/env python3
"""Bounded native profile build measurements. No runtime winner qualification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from rvw.common.proc import run_group
from rvw.cosim.trace import Trace


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--rtl',type=Path,required=True);p.add_argument('--elf',type=Path,required=True)
    p.add_argument('--reference-trace',type=Path)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--seed',type=int,default=7)
    args=p.parse_args();args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).resolve().parent;launcher=here.parent/'engine-probe.py'
    plan=json.loads((here/'plan.json').read_text())['profiles']
    report=dict(schema='rvw.native-profile-campaign/1',seed=args.seed,rtl_sha256=sha(args.rtl),
        elf_sha256=sha(args.elf),status='inconclusive',rows=[],retain_runtime_optimization=False,
        scope='one short deterministic run per profile; build/setup includes capture; execution includes Python ports and C2 publication')
    report['tools']={}
    for name,argv in [('verilator',['verilator','--version']),('compiler',['c++','--version']),('ccache',['ccache','--version'])]:
        version=run_group(argv,timeout=15,capture=True)
        report['tools'][name]=(version.stdout+version.stderr).splitlines()[0]
    def publish():(args.out/'campaign.json').write_text(json.dumps(report,indent=2)+'\n')
    reference=sha(args.reference_trace) if args.reference_trace else None
    report["reference_trace_sha256"]=reference
    cache=args.out/'ccache';cache.mkdir()
    def cache_stats():
        r=run_group(['ccache','--print-stats'],env=dict(os.environ,CCACHE_DIR=str(cache)),timeout=15,capture=True)
        return {line.split()[0]:int(line.split()[1]) for line in r.stdout.splitlines() if len(line.split())==2 and line.split()[1].isdigit()}
    for row in plan:
        name=row['name']
        if not re.fullmatch('[a-z0-9-]+',name):raise ValueError('invalid profile name')
        options={k:v for k,v in row.items() if k!='name'}
        options['schema']='rvw.native-build-profile/1'
        if options.get('ccache'):options['ccache_dir']=str(cache)
        if options.get('compiler_pgo')=='generate':options['training_elf']=str(args.elf.resolve())
        if options.get('compiler_pgo')=='use':options['reuse_manifest']=str(args.out/'compiler-pgo.json')
        config=args.out/(name+'.json');config.write_text(json.dumps(options,indent=2)+'\n')
        before=cache_stats() if options.get('ccache') else None
        out=args.out/name
        r=run_group(['nice','-n','10',sys.executable,str(launcher),'--backend','verilator',
            '--rtl',str(args.rtl.resolve()),'--elf',str(args.elf.resolve()),'--out',str(out),
            '--seed',str(args.seed),'--build-profile',str(config)],timeout=120,capture=True)
        (args.out/(name+'.log')).write_text(r.stdout+r.stderr)
        item=dict(name=name,returncode=r.returncode,timed_out=r.timed_out,status='inconclusive')
        if r.returncode==0 and not r.timed_out and (out/'result.json').is_file():
            result=json.loads((out/'result.json').read_text());trace=out/'rvfi.jsonl'
            digest=sha(trace);rows=[json.loads(line) for line in trace.read_text().splitlines()]
            checked=Trace(trace)
            try:list(checked)
            finally:checked.close()
            complete=bool(result['details'].get('c2_schema_validated') and rows[-1].get('event')=='end' and rows[-1].get('status')=='pass')
            if reference is None and result['status']=='pass' and complete:reference=digest
            item.update(status=result['status'] if complete else 'inconclusive',c2_complete=complete,c2_equal=complete and digest==reference,
                trace_sha256=digest,cycles=result['cycles'],instret=result['instret'],
                build_setup_s=result['details']['model_compile_s'],execution_trace_s=result['details']['execution_s'],
                child_peak_rss_bytes=result['details']['child_peak_rss_bytes'])
            if options.get('compiler_pgo')=='generate' and item['status']=='pass' and item['c2_equal']:
                bound=result['details']['native_profile']['binding']
                raw=Path(bound['raw']);merged=args.out/'native.profdata'
                if not raw.is_file():raise ValueError('compiler did not write a raw profile')
                profdata=shutil.which('llvm-profdata')
                if not profdata:
                    found=run_group(['xcrun','--find','llvm-profdata'],timeout=15,capture=True)
                    if found.returncode:raise ValueError('llvm-profdata required')
                    profdata=found.stdout.strip()
                merged_run=run_group(['nice','-n','10',profdata,'merge','-o',str(merged),str(raw)],timeout=30,capture=True)
                if merged_run.returncode:raise ValueError(merged_run.stderr)
                bound.update(schema='rvw.compiler-pgo/1',profile=str(merged),profile_sha256=sha(merged),
                             raw_sha256=sha(raw),merge_tool_sha256=sha(profdata))
                (args.out/'compiler-pgo.json').write_text(json.dumps(bound,indent=2)+'\n')
        if before is not None:
            after=cache_stats();item['ccache_delta']={key:after.get(key,0)-value for key,value in before.items()}
        report['rows'].append(item);publish()
    report['status']='measured_smoke' if all(row['status']=='pass' and row.get('c2_equal') for row in report['rows']) else 'inconclusive'
    publish()
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='measured_smoke' else 3

if __name__=='__main__':raise SystemExit(main())
