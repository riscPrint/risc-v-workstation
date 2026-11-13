import json
import sys
from collections import OrderedDict,Counter,defaultdict
from pathlib import Path
from rvw.ooo.core import _instructions
root=Path(sys.argv[1])
result={}
for name in ('median','multiply'):
 kinds={op.pc:op.kind for op in _instructions((root/name/'rvfi.jsonl').read_bytes())}
 live=OrderedDict();lat=defaultdict(Counter)
 with (root/name/'probe-events.jsonl').open() as f:
  header=json.loads(next(f));probes={p['id']:p for p in header['probes']}
  for line in f:
   row=json.loads(line)
   if not isinstance(row,list):continue
   cycle,pid,*values=row;p=probes[pid]
   if p['kind'] not in ('stage','flush','retire'):continue
   fields=dict(zip((x[0] for x in p['fields']),values));i=fields['id'];stage=p['meta'].get('stage')
   if stage=='Rn':
    live.pop(i,None);live[i]=dict(pc=fields['pc'])
   elif p['kind']=='flush':
    if i not in live:continue
    ids=list(live);pos=ids.index(i)+(not fields.get('inclusive',0))
    for victim in ids[pos:]:live.pop(victim,None)
   elif p['kind']=='retire':
    state=live.pop(i,{})
    if 'Is' in state and 'Wb' in state:
     kind=kinds.get(state['pc'],'unknown')
     lat[kind][state['Wb']-state['Is']]+=1
   elif i in live and stage in ('Is','Wb'):live[i][stage]=cycle
 result[name]={kind:dict(counts) for kind,counts in lat.items()}
print(json.dumps(result,indent=2))
