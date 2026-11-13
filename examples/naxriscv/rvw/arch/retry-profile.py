#!/usr/bin/env python3
"""Extract base-only retry observations. Local added recovery costs remain assumed zero."""
from collections import Counter
from hashlib import sha256
import json
import sys
from pathlib import Path
from statistics import median
from rvw.probes.events import read
from rvw.probes.retries import retry_statistics
p=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
s=read(p/'probe-events.jsonl')
r=retry_statistics(s);events=list(s.events());observations=[]
for index,(cycle,probe,values) in enumerate(events):
 if probe.kind!='lsuretry':continue
 cause=probe.meta['cause'];i=values['id'];first=None
 for c,q,v in reversed(events[:index]):
  if q.kind=='stage' and q.meta.get('first')=='true' and v['id']==i:
   first=(c,v.get('pc'));break
 if first is None:raise ValueError('orphan retry')
 observation=dict(cycle=cycle,id=i,cause=cause,pc=hex(first[1]))
 if cause=='memory_order_violation':
  flush=next((c for c,q,v in events[index+1:] if q.kind=='flush' and v['id']==i and v.get('inclusive')),None)
  restart=next((c for c,q,v in events[index+1:] if flush is not None and c>flush and q.kind=='stage' and q.meta.get('first')=='true' and v.get('pc')==first[1]),None)
  observation.update(flush_cycle=flush,restart_cycle=restart,recovery_cycles=restart-cycle if restart else None)
 else:
  for c,q,v in events[index+1:]:
   if q.kind=='stage' and q.meta.get('first')=='true' and v['id']==i:break
   if q.kind=='flush' and v['id']==i:break
   if q.kind=='stage' and q.meta.get('stage')=='Ls' and v['id']==i:
    observation['next_attempt_cycles']=c-cycle;break
 observations.append(observation)
recovery=[o['recovery_cycles'] for o in observations if o['cause']=='memory_order_violation' and o.get('recovery_cycles') is not None]
if not recovery:raise ValueError('no complete memory-order recovery')
profile={'memory_order_violation':int(median(recovery)),'store_forward_miss':0,'cache_miss_retry':0,'tlb_miss':0}
r['observations']=observations;r['retry_costs']=profile
r['cost_evidence']={'memory_order_violation':'median detection to first matching-PC rename after inclusive flush; base RTL only',
                   'local_causes':'zero added recovery is an assumption; service waits are modeled separately, not measured isolated costs'}
r['rtl']={k:json.loads((p/'result.json').read_text())[k] for k in ('status','cycles','instret','seed')}
r['spike']={k:json.loads((p/'spike.json').read_text())[k] for k in ('status','instructions','trace_complete','synchronized')}
r['captures']={f:sha256((p/f).read_bytes()).hexdigest() for f in ('probe-events.jsonl','rvfi.jsonl','result.json')}
(out/'profile.json').write_text(json.dumps(r,indent=2)+'\n')
for cache in (False,True):
 config=json.loads((Path(__file__).parent/'ooo-resource.json').read_text());config['retry_costs']=profile;config['cache_miss_replay']=cache
 (out/('ooo-typed'+('-cache' if cache else '')+'.json')).write_text(json.dumps(config,indent=2)+'\n')
print(json.dumps(observations,indent=2))
