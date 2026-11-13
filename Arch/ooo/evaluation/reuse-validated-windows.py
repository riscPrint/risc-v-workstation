"""Reuse one fully validated source across two model configurations."""
from pathlib import Path
import json
from hashlib import sha256
from rvw.ooo.core import _instruction,simulate
from rvw.ooo.project import configuration
from rvw.ooo.sampled import Window
from rvw.ooo.windows import digest
import sys
p=Path(sys.argv[1]);t=p/'trace.jsonl'
base=json.loads((p/'zen5-like.json').read_text());sp=json.loads((p/'points.json').read_text())
assert digest(t)==base['trace_sha256']==sp['source_c2_sha256']
points=sp['points'];ranges=[(max(0,x['start_instruction']-200),x['start_instruction']+x['instructions']) for x in points];windows=[[] for x in points];count=0
with t.open() as f:
 header=json.loads(next(f))
 for line in f:
  if '"event"' in line:
   continue  # Already checked by the complete first-model validation.
  selected=[i for i,(lo,hi) in enumerate(ranges) if lo<=count<hi]
  if selected:
   row=json.loads(line)
   row={k:int(v,16) if isinstance(v,str) and v.startswith('0x') else v for k,v in row.items()}
   op=_instruction(row,header['xlen'])
   for i in selected:windows[i].append(op)
  count+=1
assert count==sp['instructions']
assert digest(t)==base['trace_sha256']
for model in ('zen5-like','m1-like'):
 cp=p.parent/(model+'.json');c=configuration(json.loads(cp.read_text()));samples=[];cpi=0
 for point,window,(lo,hi) in zip(points,windows,ranges):
  warmup=point['start_instruction']-lo;observer=Window(warmup)
  result=simulate(window,c,10000000,backend='python',observer=observer);cycles=observer.cycles()
  samples.append(dict(point=point,warmup=warmup,cycles=cycles,instret=point['instructions'],ipc=point['instructions']/cycles,model_cycles_including_warmup=result['cycles']))
  cpi+=point['weight']*cycles/point['instructions']
 if model=='zen5-like':
  assert samples==base['samples'],'reused window timing differs from fully validated baseline'
 else:
  report={**base,'config_sha256':digest(cp),'samples':samples,'sampled_cpi':cpi,'sampled_ipc':1/cpi,'estimated_cycles':cpi*count}
  report['limits']=base['limits']+['reuses windows from the same complete C2 source validated for the first model; raw byte hashes checked before and after extraction']
  target=p/(model+'.json')
  with target.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
  print(report['sampled_ipc'])
