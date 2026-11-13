#!/usr/bin/env python3
"""Check full-program DUT-order Spike replay and one fault per hart."""
import argparse,hashlib,json,runpy
from pathlib import Path
from rvw.common.proc import run_group
root=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--run-suffix',default='')
a=p.parse_args();base=a.inputs.resolve()
exe=root/'rvw/.venv/bin/rvw'
summarize=runpy.run_path(str(Path(__file__).with_name('summarize.py')))['summarize']
def check(trace):
 r=run_group([str(exe),'--project','examples/smp/rvw.toml','cosim','check','--elf',str(base/'shared.elf'),'--trace',str(trace),'--json'],capture=True,timeout=90)
 if r.timed_out:raise RuntimeError('Spike comparison timed out')
 try:
  report=json.loads(r.stdout)
  if report['status']=='match' and r.returncode!=0:raise RuntimeError('match returned a failing exit code')
  if report['status']=='mismatch' and r.returncode!=1:raise RuntimeError('mismatch returned an unexpected exit code')
  return report
 except ValueError:raise RuntimeError(r.stdout+r.stderr)
reports=[]
for seed in (17,23):
 trace=base/f'run-{seed}{a.run_suffix}/rvfi.jsonl';report=check(trace)
 assert report['status']=='match',report
 rtl=summarize(trace.parent)
 assert rtl['status']=='pass',rtl
 reports.append(dict(seed=seed,trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),rtl=rtl,result=report))
rows=[json.loads(line) for line in (base/f'run-17{a.run_suffix}/rvfi.jsonl').read_text().splitlines()]
negative=[]
for hart in (0,1):
 copy=[dict(row) for row in rows]
 r=next(row for row in copy if 'event' not in row and row.get('hart')==hart and row.get('rd',0)!=0)
 r['rd_wdata']=hex(int(r['rd_wdata'],0)^1)
 target=base/f'fault-hart-{hart}.jsonl';target.write_text(''.join(json.dumps(r)+'\n' for r in copy))
 report=check(target)
 assert report['status']=='mismatch' and report['hart']==hart,report
 negative.append(dict(injected_hart=hart,result=report))
result=dict(schema='rvw.smp-full-replay/1',scope='serialized DUT retirement order drives shared-memory Spike; not a weak-memory oracle',runs=reports,negative_controls=negative)
def concise(value):
 if isinstance(value,dict):return {k:concise(v) for k,v in value.items() if k not in ('reproduction','event_order')}
 if isinstance(value,list):return [concise(v) for v in value]
 return value
text=json.dumps(concise(result),indent=2).replace(str(root),'$CHECKOUT').replace(str(Path.home()),'~')
(base/'replay-results.json').write_text(text+'\n')
print(text)
