#!/usr/bin/env python3
"""Collect one-structure mini-core runs and require complete Spike matches."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = {'default': {}, 'rob16': {'rob_entries': 16}, 'iq4': {'issue_entries': 4},
            'sq4': {'store_entries': 4}, 'predictor4': {'predictor_entries': 4}}
PROGRAMS = ('median', 'qsort', 'multiply', 'towers', 'vvadd', 'memcpy', 'rob-pressure', 'iq-pressure', 'sq-pressure')


def main(bench, output):
    bench, output = Path(bench).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rvw = Path(sys.executable).with_name('rvw')
    rows = []
    incomplete = []
    for config, changes in VARIANTS.items():
        missing=[p for p in PROGRAMS if not (output/config/p/'result.json').exists()]
        (output/config).mkdir(parents=True,exist_ok=True)
        def execute(command,log):
            with log.open('w') as f:
                args=list(map(str,command))
                env=os.environ.copy()
                if args[:3]==['nice','-n','10']:
                    if os.getpriority(os.PRIO_PROCESS,0)>=10:args=args[3:]
                    # The worker is already niced. Do not add ten again in run.sh.
                    env.setdefault('RVW_NICE','0')
                subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True,env=env)
        if missing:
            subprocess.run(['df','-h','/System/Volumes/Data'],check=True)
            if shutil.disk_usage('/System/Volumes/Data').free < 15*1024**3:
                raise RuntimeError('native work stopped: less than 15 GiB free')
            manifest=output/(config+'-jobs.jsonl')
            jobs=[dict(config=config,elf=str(bench/(p+'.riscv')),out=str(output/config/p),
                       seed=1,mem_latency=0,max_cycles=1000000,wall_timeout=120,rvfi_trace=True)
                  for p in missing]
            manifest.write_text(''.join(json.dumps(j)+'\n' for j in jobs))
            try:
                execute(['nice','-n','10',ROOT/'rvw/run.sh','run-many','--manifest',manifest,
                         '--jobs',1,'--wall-timeout',120,'--json'],output/(config+'-native.log'))
            except subprocess.CalledProcessError:
                pass  # Each failed or missing C1 stays explicit below. No sample is accepted here.
        for program in PROGRAMS:
            dest=output/config/program
            elf=bench/(program+'.riscv')
            result_path=dest/'result.json'
            result=json.loads(result_path.read_text()) if result_path.exists() else {'status':'missing'}
            if result['status']!='pass':
                incomplete.append(dict(config=config,program=program,status=result['status'],
                                       cycles=result.get('cycles'),instret=result.get('instret')))
                (output/'incomplete.json').write_text(json.dumps(incomplete,indent=2)+'\n')
                continue
            if not (dest/'spike.json').exists():
                execute(['nice','-n','10',rvw,'--project',ROOT,'cosim','check','--elf',elf,
                         '--trace',dest/'rvfi.jsonl','--json'],dest/'spike.json')
            spike=json.loads((dest/'spike.json').read_text())
            if (spike['status']!='match' or not spike['trace_complete'] or spike['instructions']!=result['instret']
                   ):
                raise RuntimeError(f'{config}/{program}: no complete Spike match')
            row=dict(config=config,program=program,changes=changes,cycles=result['cycles'],instret=result['instret'],
                     ipc=result['instret']/result['cycles'],spike={k:spike[k] for k in ('status','instructions','trace_complete','synchronized')},
                     hashes={f:hashlib.sha256((dest/f).read_bytes()).hexdigest() for f in ('result.json','rvfi.jsonl','probe-events.jsonl') if (dest/f).exists()},
                     elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())
            rows.append(row)
            (output/'rtl-summary.json').write_text(json.dumps(rows,indent=2)+'\n')
            print(config,program,result['cycles'],flush=True)
    (output/'incomplete.json').write_text(json.dumps(incomplete,indent=2)+'\n')
    if incomplete:raise RuntimeError('matrix is inconclusive: incomplete RTL cases remain')


if __name__=='__main__':main(*sys.argv[1:])
