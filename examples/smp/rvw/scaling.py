#!/usr/bin/env python3
"""Prepare and check N=2..8 smoke and PLIC CPU races."""
def source(h,harts,rounds=8):
 return f''' .option norvc
.text
.globl _start
_start:
li s0, 0x81000000
li t0, 0xc000004
li t1, 1
sw t1, 0(t0)
li t0, {0xc002000+h*0x80}
li t1, 2
sw t1, 0(t0)
li s1, {0xc200004+h*0x1000}
li s2, {rounds}
round:
fence rw, rw
lw s3, 0(s1)
beqz s3, lost
li t0, 1
bne s3, t0, fail
amoadd.d.aqrl zero, t0, (s0)
lw t1, 0(s1)
bnez t1, fail
lost:
li t0, 1
addi t2, s0, 8
amoadd.d.aqrl zero, t0, (t2)
wait1:
ld t1, 0(t2)
li t3, {harts}
bne t1, t3, wait1
ld t1, 0(s0)
li t3, 1
bne t1, t3, fail
beqz s3, no_complete
sw s3, 0(s1)
no_complete:
li t0, 1
addi t2, s0, 16
amoadd.d.aqrl zero, t0, (t2)
wait2:
ld t1, 0(t2)
li t3, {harts}
bne t1, t3, wait2
addi s0, s0, 32
addi s2, s2, -1
bnez s2, round
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

def check_plic(plic):
 claims,completions=plic['claims'],plic['completions']
 if sum(claims)!=8 or claims!=completions:raise ValueError('PLIC context counts differ')


def timing_prepare(root):
 import json,runpy
 from pathlib import Path
 program=runpy.run_path(str(Path(__file__).with_name('programs.py')))
 root.mkdir(parents=True,exist_ok=False);jobs=[]
 for h in range(2,9):
  folder=root/f'inputs-{h}'
  sources=[program['assembly'](i,'smoke').replace('li a0, 1\nj finish',
      'li s1, 1000\ntiming_loop:\naddi s1, s1, -1\nbnez s1, timing_loop\nli a0, 1\nj finish') for i in range(h)]
  program['build'](folder,harts=h,sources=sources)
  for repeat in range(4):
   jobs.append(dict(elf=str(folder/'hart-0.elf'),hart_images=str(folder/'hart-images.json'),
       out=str(root/f'timing-{h}-{repeat}-run'),config=f'smp{h}',seed=17,max_cycles=30000,wall_timeout=90,rvfi_trace=True))
 (root/'jobs.jsonl').write_text(''.join(json.dumps(j)+'\n' for j in jobs))


def timing_summarize(root,log):
 import json,re,runpy,statistics
 from pathlib import Path
 summary=runpy.run_path(str(Path(__file__).with_name('summarize.py')))['summarize']
 text=Path(log).read_text()
 header=re.search(r'^\[run-many\] \d+ jobs, (\d+) workers$',text,re.M)
 if not header or header.group(1)!='1':raise ValueError('one run-many worker is required for timing')
 times={};name=None
 for line in text.splitlines():
  m=re.match(r'\[([^#]+)#\d+\] run ',line)
  if m:name=m.group(1)
  m=re.search(r'\[Done\] Simulation done in ([0-9.]+) ms',line)
  if m and name:times[name]=round(float(m.group(1))/1000,6)
 rows=[];common=None
 for h in range(2,9):
  folders=[root/f'timing-{h}-{repeat}-run' for repeat in range(4)]
  runs=[summary(folder) for folder in folders]
  if not all(r['status']=='pass' and len(r['per_hart_retirements'])==h for r in runs):raise ValueError(('incomplete hart set',runs))
  if len({r['trace_sha256'] for r in runs})!=1:raise ValueError(('replay differs',runs))
  for folder in folders:
   c1=json.loads((folder/'result.json').read_text())
   if c1['config']!=f'smp{h}':raise ValueError('configuration differs from hart count')
   controls={key:c1['details']['timing'][key] for key in ('random_max_delay','ready_percent','clock_enable_percent','fixed_latency')}
   actual=(c1['seed'],controls)
   if common is None:common=actual
   if actual!=common:raise ValueError('timing controls differ')
  samples=[times[r['run']] for r in runs[1:]]
  rows.append(dict(harts=h,cycles=runs[0]['cycles'],instret=runs[0]['instret'],
      simulation_wall_samples=samples,median_simulation_wall_s=statistics.median(samples),
      trace_sha256=runs[0]['trace_sha256'],replay='four byte-identical captures',core_rev=runs[0]['core_rev']))
 report=dict(schema='rvw.smp-timing/1',seed=common[0],loop_iterations=1000,
     timing=common[1],runs=rows,scope='one warmup then three samples per N on a shared host; model build excluded')
 (root/'timing-results.json').write_text(json.dumps(report,indent=2)+'\n')
 return report


if __name__ == '__main__':
 import argparse,json,runpy,re
 from pathlib import Path
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','summarize','timing-prepare','timing-summarize']);p.add_argument('--out',required=True);p.add_argument('--log')
 a=p.parse_args();root=Path(a.out).resolve()
 if a.action=='timing-prepare':timing_prepare(root);raise SystemExit(0)
 if a.action=='timing-summarize':timing_summarize(root,a.log);raise SystemExit(0)
 if a.action=='prepare':
  build=runpy.run_path(str(Path(__file__).with_name('programs.py')))['build']
  root.mkdir(parents=True,exist_ok=False);jobs=[]
  for h in range(2,9):
   for suite in ('smoke','plic-race'):
    name=f'{suite}-{h}';folder=root/name
    build(folder,harts=h,sources=[source(i,h) for i in range(h)] if suite=='plic-race' else None)
    jobs.append(dict(elf=str(folder/'hart-0.elf'),hart_images=str(folder/'hart-images.json'),out=str(root/(name+'-run')),config=f'smp{h}',seed=17,max_cycles=200000,wall_timeout=180,rvfi_trace=True))
  (root/'jobs.jsonl').write_text(''.join(json.dumps(j)+'\n' for j in jobs))
 else:
  summary=runpy.run_path(str(Path(__file__).with_name('summarize.py')))['summarize'];times={};name=None
  if a.log:
   for line in Path(a.log).read_text().splitlines():
    m=re.match(r'\[([^#]+)#\d+\] run ',line)
    if m:name=m.group(1)
    m=re.search(r'\[Done\] Simulation done in ([0-9.]+) ms',line)
    if m and name:times[name]=float(m.group(1))/1000
  rows=[]
  for job in map(json.loads,(root/'jobs.jsonl').read_text().splitlines()):
   folder=Path(job['out']);r=summary(folder);c1=json.loads((folder/'result.json').read_text());r['plic']=c1['details']['plic'];r['timing']=c1['details']['timing'];r['c1_wall_s']=c1['wall_s'];r['simulation_wall_s']=times.get(folder.name)
   if 'plic-race' in folder.name:
    check_plic(r['plic'])
   if r['status']!='pass':raise ValueError(('run did not pass',r))
   rows.append(r)
  (root/'scaling-results.json').write_text(json.dumps(dict(schema='rvw.smp-scaling/1',runs=rows,scope='finite cacheless RTL runs; PLIC is a simulation model; simulation time excludes model build'),indent=2)+'\n')
