"""Event and bounded sequence goals over qualified project probe streams."""
import json
from pathlib import Path
from . import captured
from .rtl import identity
from rvw.results import load_run
from rvw.probes.events import read
from rvw.regress.random_stream import complete,digest
from rvw.cosim.cli import execute_json as cosim


@captured.command
def probe_goals(result, plan, platform):
    run=load_run(result)
    events,trace=run.artifact('probe_events'),run.artifact('rvfi_trace')
    if run.why_inconclusive or run.status!='pass' or events is None or trace is None:
        raise ValueError('probe goals need passing C1 with complete C2 and probe events')
    elf=run.artifact('replay_elf') or Path(run.elf)
    if not elf.is_absolute(): elf=run.path/elf
    if digest(elf)!=run.elf_sha256:
        raise ValueError('C1 ELF hash differs')
    stream=read(events)
    if not stream.end or stream.end.get('cycles')!=run.cycles:
        raise ValueError('probe stream is incomplete or cycles differ from C1')
    for key,value in [('core',run.core),('config',run.config),('elf_sha256',run.elf_sha256),
                      ('rtl_sha256',run.extra.get('rtl_sha256')),('seed',run.seed)]:
        if value is None or stream.identity.get(key)!=value:
            raise ValueError('probe identity differs: '+key)
    data=json.loads(captured.read_text(plan))
    if data.get('schema')!='rvw.probe-goals/1' or data.get('design')!=stream.identity['rtl_sha256']:
        raise ValueError('probe goals need exact generated RTL identity')
    probes={(p.kind,p.name):p for p in stream.probes}
    if len(probes)!=len(stream.probes):
        raise ValueError('probe kind/name pairs must be unique')
    bins=data['bins'];sequences=data.get('sequences',[])
    if not bins:
        raise ValueError('plan needs at least one event bin')
    ids=[b['id'] for b in bins]+[s['id'] for s in sequences]
    if len(ids)!=len(set(ids)) or not all(isinstance(i,str) and i for i in ids):
        raise ValueError('goal IDs must be unique')
    by_id={b['id']:b for b in bins}
    for b in bins:
        p=probes.get((b['kind'],b['name']))
        if p is None or set(b.get('fields',{}))-set(p.names):
            raise ValueError('goal needs a declared probe and fields')
        widths=dict(p.fields)
        for name,values in b.get('fields',{}).items():
            if not values or any(type(v) is not int or not 0<=v<2**widths[name] for v in values):
                raise ValueError('goal values exceed probe field width')
    selected={probes[(b['kind'],b['name'])].id for b in bins}
    for pid in selected:
        p=stream.probes[pid]
        rows=[(cycle,values) for cycle,i,values in stream.rows if i==pid]
        if p.kind=='counter' or stream.end.get('events',{}).get(str(pid),0)!=len(rows):
            raise ValueError('goal needs complete per-cycle probe event accounting')
        for cycle,values in rows:
            if not 0<=cycle<=run.cycles or any(width<1 or not 0<=v<2**width for (_,width),v in zip(p.fields,values)):
                raise ValueError('probe row exceeds cycle or field bounds')
    for s in sequences:
        if (len(s['steps'])<2 or set(s['steps'])-by_id.keys() or
                type(s['max_gap']) is not int or s['max_gap']<1):
            raise ValueError('sequence needs declared bin steps and positive max_gap')
    comparison=cosim('check',elf=str(elf),trace=str(trace),platform=str(platform),core=run.core,model='spike',strict=True)
    if not complete(comparison,run):
        raise ValueError('probe goals need a complete strict Spike match')
    counts={i:0 for i in by_id};completed={s['id']:0 for s in sequences};pending={s['id']:[] for s in sequences}
    cycles={}
    for cycle,probe,values in stream.events():
        hit=cycles.setdefault(cycle,set())
        for b in bins:
            if (probe.kind,probe.name)==(b['kind'],b['name']) and all(values[k] in v for k,v in b.get('fields',{}).items()):
                counts[b['id']]+=1;hit.add(b['id'])
    for cycle,hits in sorted(cycles.items()):
        for s in sequences:
            following=[]
            for step,last in pending[s['id']]:
                if cycle-last>s['max_gap']:continue
                if cycle>last and s['steps'][step] in hits:
                    if step+1==len(s['steps']):completed[s['id']]+=1
                    else:following.append((step+1,cycle))
                else:following.append((step,last))
            if s['steps'][0] in hits:following.append((1,cycle))
            pending[s['id']]=list(set(following))
    for s in sequences:
        pending[s['id']]=[(step,last) for step,last in pending[s['id']]
            if stream.end['cycles']-last<=s['max_gap']]
    return {'schema':'rvw.probe-coverage/1','status':'qualified','design':data['design'],
            'plan_id':identity(data),
            'plan_sha256':captured.sha256(plan),'result_sha256':captured.sha256(result),
            'events_sha256':captured.sha256(events),'trace_sha256':captured.sha256(trace),
            'comparison':{k:comparison[k] for k in ('status','instructions','trace_complete','synchronized','applied_masks')},
            'bins':[dict(id=i,count=n) for i,n in counts.items()],
            'sequences':[dict(id=i,completed=n,pending=len(pending[i])) for i,n in completed.items()],
            'holes':sorted([i for i,n in counts.items() if not n]+[i for i,n in completed.items() if not n]),
            'notes':['Probe definitions and source associations come from the project.',
                     'Sequences use increasing cycles and one common per-step max_gap.',
                     'Repeated identical pending states collapse; counts are completed monitor states, not all possible event tuples.',
                     'Qualification covers C1 and full C2/Spike execution. Probe wiring remains project-owned.',
                     'This report does not grant C4 acceptance or whole-core coverage.']}
