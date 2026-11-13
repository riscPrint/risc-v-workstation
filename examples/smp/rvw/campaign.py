#!/usr/bin/env python3
"""Fixed-budget SMP campaign. Never infer ordering from completion alone."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def contention(hart, harts, iterations=32):
    """All harts increment one word with LR/SC, then check the shared sum."""
    return f''' .option norvc
.text
.globl _start
_start:
li s0, 0x81000000
li s1, {iterations}
loop:
lr.d.aq t0, (s0)
addi t0, t0, 1
sc.d.rl t1, t0, (s0)
bnez t1, loop
addi s1, s1, -1
bnez s1, loop
fence rw, rw
li t0, 1
addi s2, s0, 8
amoadd.d.aqrl zero, t0, (s2)
barrier:
ld t1, 0(s2)
li t2, {harts}
bne t1, t2, barrier
fence rw, rw
ld t1, 0(s0)
li t2, {harts*iterations}
bne t1, t2, fail
li a0, 1
j finish
fail:
li a0, 3
finish:
la t0, tohost
sd a0, 0(t0)
park: j park
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
.section .shared,"aw",@nobits
.zero 512
'''


def prepare(out, tests, seeds=16, length=16):
    from rvw.memory.concurrent_build import build as random_build
    programs = runpy.run_path(str(HERE/'programs.py'))['build']
    suites = runpy.run_path(str(HERE/'suite_programs.py'))['build']
    litmus = runpy.run_path(str(HERE/'litmus_programs.py'))['build']
    pins = json.loads((ROOT/'RiscvSim/tests/ordering/litmus-pins.json').read_text())
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    jobs = []
    def add(name, harts, seed, kind):
        jobs.append(dict(elf=str(out/name/'hart-0.elf'), hart_images=str(out/name/'hart-images.json'),
                         out=str(out/(name+'-run')), config=f'smp{harts}', seed=seed,
                         max_cycles=200000, wall_timeout=120, rvfi_trace=True))
        return dict(name=name, harts=harts, seed=seed, kind=kind)
    cases = []
    for test in pins['cases']:
        name='litmus-'+Path(test).stem
        litmus(Path(tests)/test,out/name)
        cases.append(add(name,2,17,'litmus'))
    for seed in range(1,seeds+1):
        name=f'random-{seed}'
        built=random_build(out/name,seed=seed,harts=2,length=length)
        if built['status']!='built': raise ValueError(built)
        cases.append(add(name,2,seed,'random'))
    for h in range(2,5):
        for kind in ('lrsc-contention','amo'):
            name=f'{kind}-{h}'
            if kind=='amo': suites(out/name,'amo',17,h)
            else: programs(out/name,harts=h,sources=[contention(i,h) for i in range(h)])
            cases.append(add(name,h,17,kind))
    (out/'jobs.jsonl').write_text(''.join(json.dumps(j)+'\n' for j in jobs))
    (out/'campaign.json').write_text(json.dumps(dict(seeds=seeds,length=length,cases=cases),indent=2)+'\n')
    return out/'jobs.jsonl'


def summarize(out):
    from rvw.memory.axiomatic import check
    summary=runpy.run_path(str(HERE/'summarize.py'))['summarize']
    bind=runpy.run_path(str(HERE/'scalar_dependencies.py'))['bind']
    out=Path(out).resolve()
    spec=json.loads((out/'campaign.json').read_text())
    rows=[]
    for case in spec['cases']:
        name=case['name']; folder=out/(name+'-run')
        row=case | summary(folder)
        c1=json.loads((folder/'result.json').read_text())
        row['timing']=c1['details']['timing']
        if case['kind']=='random' and row['status']=='pass':
            derived=folder/'dependencies.jsonl'
            if not derived.exists(): bind(folder/'rvfi.jsonl',derived)
            start=time.monotonic()
            result=check(derived,out/name/'initial.json')
            row['checker_seconds']=time.monotonic()-start
            result.pop('witness',None)
            row['axiomatic']=result
        rows.append(row)
    report=dict(schema='rvw.smp-campaign/1',budget=dict(seeds=spec['seeds'],length=spec['length']),
                completion_counts=dict(Counter(r['status'] for r in rows)),
                ordering_counts=dict(Counter(r['axiomatic']['status'] for r in rows if 'axiomatic' in r)),
                runs=rows)
    (out/'campaign-results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','summarize'])
    p.add_argument('--out',required=True);p.add_argument('--tests')
    a=p.parse_args()
    print(prepare(a.out,a.tests) if a.action=='prepare' else json.dumps(summarize(a.out),indent=2))
